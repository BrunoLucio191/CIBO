"""Gera captions.json (tempo editado) a partir do JSON de palavras do Whisper large-v3 e do job.

Uso: python3 build_captions.py job.json whisper_large.json saida.json
- descarta palavras dentro de job["cuts"] e fora de [in, out];
- descarta repeticao imediata identica (alucinacao do large-v3 em arquivo longo: confira no trecho isolado antes de cortar);
- aplica job["caption_fixes"] (palavra exata -> correcao), p.ex. termos que ela pronuncia de outro jeito;
- blocos de ate 22 caracteres (25 se fechar frase), quebra em pontuacao, nunca termina em palavra funcional.
Revise o resultado a mao: quebras finais e nomes do produto costumam precisar de ajuste.
"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from timeline import load_job, o, duration

job = load_job(sys.argv[1])
d = json.load(open(sys.argv[2]))
D = duration(job)
FIX = job.get("caption_fixes", {})
cuts = job.get("cuts", [])
words = []
for s in d["segments"]:
    for w in s["words"]:
        t = w["word"].strip()
        if not (job["in"] <= w["start"] < job["out"]) or any(a - 0.05 <= w["start"] < b for a, b in cuts):
            continue
        key = t.lower().strip(",.?!")
        if words and key == words[-1][0].lower().strip(",.?!") and key not in ("a", "o", "e"):
            continue
        words.append([FIX.get(t, t), o(job, w["start"]), o(job, w["end"])])
merged = []
for w in words:
    if w[0] == "%" and merged:
        merged[-1][0] += "%"; merged[-1][2] = w[2]
    else:
        merged.append(w)
words = merged

MAX = 22
FUNC = {"o", "a", "os", "as", "um", "uma", "e", "de", "da", "do", "das", "dos", "na", "no", "com", "que", "sem", "em",
        "se", "por", "para", "essas", "esse", "sua", "seu", "nossa", "nosso", "ter", "é", "à", "ali", "já", "você"}
caps, cur = [], []
txt = lambda ws: " ".join(x[0] for x in ws)


def flush():
    global cur
    if not cur:
        return
    carry = []
    while len(cur) > 1 and cur[-1][0].lower() in FUNC:
        carry.insert(0, cur.pop())
    caps.append({"text": txt(cur), "start": cur[0][1], "wend": cur[-1][2]})
    cur = carry


for w in words:
    L = len(txt(cur + [w]))
    over = L > MAX and not (re.search(r"[.?!]$", w[0]) and L <= 25)
    if cur and (over or w[1] - cur[-1][2] > 0.45):
        flush()
    cur.append(w)
    if re.search(r"[.?!]$", w[0]) or (re.search(r",$", w[0]) and len(txt(cur)) >= 8):
        flush()
while cur:
    flush()
for i, c in enumerate(caps):
    nxt = caps[i + 1]["start"] if i + 1 < len(caps) else D
    c["end"] = round(min(nxt, c["wend"] + 0.5, D - 0.05), 3)
    c["start"] = round(c["start"], 3)
    del c["wend"]
json.dump(caps, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
for c in caps:
    dur = max(c["end"] - c["start"], 0.01)
    print(f'{c["start"]:6.2f}-{c["end"]:6.2f} {len(c["text"]):2d}c {len(c["text"]) / dur:4.1f}cps  {c["text"]}')
