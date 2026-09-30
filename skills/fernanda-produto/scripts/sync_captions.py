"""Sincroniza os blocos de legenda (texto ja revisado a mao) com a fala do video editado.

Uso: python3 sync_captions.py job.json --audio master16k.wav --words edit_large.json [--lead 0.04]

- O texto vem de job["captions"] (com "\\n" de quebra manual) e NAO e alterado.
- O Whisper so localiza as palavras (alinhamento por difflib entre texto da legenda e transcricao do audio editado).
- O tempo de entrada vai para o ATAQUE real da fala no envelope (silencio -> voz), porque o tempo de palavra do
  Whisper oscila 0,1-0,4 s entre execucoes: legenda entrando 0,3 s depois da fala foi achada no pente-fino.
- Saida: depois do ultimo fonema do bloco (+0,45 s no maximo), sem invadir o bloco seguinte nem o fim do video.
"""
import argparse, json, os, re, subprocess, sys, unicodedata, difflib
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from timeline import load_job, segments, duration, o

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("--audio", required=True); ap.add_argument("--words", required=True)
ap.add_argument("--lead", type=float, default=0.04, help="quanto a legenda entra antes do ataque")
a = ap.parse_args()
job = load_job(a.job); D = duration(job)
caps = json.load(open(job["captions"]))

from speech import edited_envelope, onset, offset
env = edited_envelope(a.audio, segments(job)); n = len(env)

def nrm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", s)

W = [w for sg in json.load(open(a.words))["segments"] for w in sg["words"]]
from speech import align
first, last = align(caps, W)

starts, ends = [], []
for i, c in enumerate(caps):
    if i in first:
        ws, we = W[first[i]]["start"], W[last[i]]["end"]
        on = onset(env, ws, W[first[i]]["end"])
        starts.append(max(0.0, (on if on is not None else ws) - a.lead)); ends.append(we)
    else:
        starts.append(None); ends.append(None)
for i in range(len(caps)):               # bloco sem palavra alinhada: entre os vizinhos
    if starts[i] is None:
        p = next((starts[k] for k in range(i - 1, -1, -1) if starts[k] is not None), 0.0)
        q = next((starts[k] for k in range(i + 1, len(caps)) if starts[k] is not None), D)
        starts[i] = (p + q) / 2; ends[i] = q
# caption_pins: ajuste manual do editor para o que nenhuma regra resolve {inicio do texto: tempo do ORIGINAL}
# (em tempo do original, como o resto do job: pino em tempo editado quebrava a cada aparo de corte)
for i, c in enumerate(caps):
    for pref, t in job.get("caption_pins", {}).items():
        if c["text"].replace("\n", " ").startswith(pref): starts[i] = o(job, float(t))
if starts[0] < 0.15: starts[0] = 0.0
for i in range(1, len(starts)):          # ordem crescente, bloco com pelo menos 0,3 s
    starts[i] = max(starts[i], starts[i - 1] + 0.3)
for i, c in enumerate(caps):
    nxt = starts[i + 1] if i + 1 < len(caps) else D - 0.05
    c["start"] = round(starts[i], 3)
    # fim: o fim REAL da fala do bloco (o Whisper terminou "intoxicada" 0,6 s antes do "-da") + 0,25 s de leitura
    fala_fim = offset(env, ends[i], nxt)
    c["end"] = round(min(nxt, max(ends[i] + 0.45, fala_fim + 0.25, c["start"] + 0.5), D - 0.05), 3)
json.dump(caps, open(job["captions"], "w"), ensure_ascii=False, indent=1)
for c in caps:
    L = len(re.sub(r"\s", "", c["text"])); d = c["end"] - c["start"]
    print(f'{c["start"]:6.2f}-{c["end"]:6.2f} {L / d:4.1f}cps  {c["text"]!r}')
