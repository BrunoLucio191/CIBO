# -*- coding: utf-8 -*-
"""Etapa 1 — tempo de cada palavra (adaptado do align.py do Bombordo).

TEXTO = job["captions"] (revisado a mao, com as quebras de linha por sentido; ja sincronizado pelo sync_captions.py).
TEMPO = palavras do Whisper large-v3 no audio EDITADO (job["word_timing"]), alinhadas ao texto por difflib.
Ataque: primeiro o onset calibrado na Malu (speech.onset: so aceita ataque depois de silencio real); dentro de fala
continua, a subida de energia perto do tempo do Whisper (snap do Bombordo). A primeira palavra de cada bloco usa o
inicio ja verificado do bloco (sync_captions + caption_pins), que e o ataque real.
Saida: <work>/kinetic/words.json (editavel: w, s, e por palavra, em tempo do video editado).
"""
import difflib, os
import numpy as np
from common import norm, display, kdir, jload, jsave, fern_path

SYNC_LEAD = 0.04          # o sync_captions.py poe o bloco 40 ms antes do ataque


def snap_rise(lin, s, before=0.10, after=0.08):
    """Subida de energia mais proxima de s (fala continua, sem silencio antes)."""
    i0, i1 = max(1, int((s - before) * 100)), min(len(lin) - 1, int((s + after) * 100))
    if i1 <= i0: return s
    seg = lin[i0:i1 + 1]
    floor = float(np.percentile(lin[max(0, i0 - 30):i1 + 30], 10))
    peak = float(lin[i0:min(len(lin), i1 + 25)].max())
    thr = floor + 0.3 * (peak - floor)
    for k in range(1, len(seg)):
        if seg[k] >= thr and seg[k - 1] < thr:
            return round((i0 + k - 1) / 100.0, 3)
    return s


def build(job, cfg):
    fern_path(job)
    from timeline import segments
    from speech import edited_envelope, onset
    caps = jload(job["captions"])
    ref = []
    for bi, c in enumerate(caps):
        for li, line in enumerate(c["text"].split("\n")):
            for w in line.split():
                ref.append(dict(w=w, blk=bi, line=li, cs=c["start"], ce=c["end"]))
    wt = job.get("word_timing") or os.path.join(job["work"], "edit_whisper-large-v3-mlx.json")
    asr = [(w["word"].strip(), float(w["start"]), float(w["end"]))
           for s in jload(wt)["segments"] for w in s.get("words", []) if w["word"].strip()]
    env = edited_envelope(job["audio16k"], segments(job)); lin = 10 ** (env / 20)
    rn, an = [norm(r["w"]) for r in ref], [norm(x[0]) for x in asr]
    sm = difflib.SequenceMatcher(None, rn, an, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for d in range(i2 - i1):
                r, x = ref[i1 + d], asr[j1 + d]
                if r["cs"] - 0.6 <= x[1] <= r["ce"] + 0.6:
                    r["s"], r["e"], r["src"] = x[1], x[2], "asr"
    # palavras que o ouvido nao confirmou: interpoladas dentro da janela do proprio bloco, pelo tamanho
    i = 0
    while i < len(ref):
        if "src" in ref[i]: i += 1; continue
        j = i
        while j < len(ref) and "src" not in ref[j] and ref[j]["blk"] == ref[i]["blk"]: j += 1
        same = lambda k: 0 <= k < len(ref) and "src" in ref[k] and ref[k]["blk"] == ref[i]["blk"]
        lo = ref[i - 1]["e"] if same(i - 1) else ref[i]["cs"]
        hi = ref[j]["s"] if same(j) else ref[i]["ce"]
        hi = max(hi, lo + 0.12 * (j - i))
        tot = sum(len(ref[k]["w"]) + 1 for k in range(i, j)); t = lo
        for k in range(i, j):
            d = (hi - lo) * (len(ref[k]["w"]) + 1) / tot
            ref[k]["s"], ref[k]["e"], ref[k]["src"] = round(t, 3), round(t + d, 3), "interp"; t += d
        i = j
    prev = -9.0
    for r in ref:
        if r["src"] == "asr":
            ws = r["s"]
            on = onset(env, ws, r["e"])
            # so aceita o ataque "depois de silencio" se houver pausa real (>= 150 ms): o fechamento do /p/ de
            # "passa" (~70 ms mudo) virava pausa e puxava a palavra 0,13 s para frente
            real = on is not None and abs(on - ws) <= 0.25 and (env[max(0, int(on * 100) - 15):int(on * 100)] < -40).all()
            r["s"] = on if real else snap_rise(lin, ws)
            # duas palavras nunca dividem o mesmo ataque ("passa para": as duas iam para 20,67 s e "passa" virava
            # um bloco de 40 ms); a segunda volta para o tempo do Whisper
            if r["s"] <= prev + 0.06: r["s"] = max(ws, prev + 0.06)
        prev = r["s"]
    for bi, c in enumerate(caps):                  # ataque verificado do bloco (sync_captions / caption_pins)
        first = next(r for r in ref if r["blk"] == bi)
        first["s"], first["src"] = round(c["start"] + SYNC_LEAD, 3), "bloco"
    for k in range(len(ref)):                      # monotonico, sem sobreposicao, duracao minima
        if k and ref[k]["s"] < ref[k - 1]["s"] + 0.04: ref[k]["s"] = round(ref[k - 1]["s"] + 0.04, 3)
        ref[k]["e"] = round(max(ref[k]["e"], ref[k]["s"] + 0.08), 3)
        if k + 1 < len(ref): ref[k]["e"] = round(min(ref[k]["e"], max(ref[k + 1]["s"], ref[k]["s"] + 0.04)), 3)
    words = [dict(w=r["w"], d=display(r["w"]), s=round(r["s"], 3), e=round(r["e"], 3), blk=r["blk"], line=r["line"],
                  src=r["src"]) for r in ref]
    div = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            div.append(dict(legenda=" ".join(r["w"] for r in ref[i1:i2]), ouvido=" ".join(x[0] for x in asr[j1:j2])))
    out = dict(note="edite w/d/s/e a vontade (tempo do video editado); d = texto na tela", words=words,
               divergencias_asr=div, confirmadas_asr=sum(1 for r in ref if r["src"] == "asr"), total_palavras=len(ref))
    p = os.path.join(kdir(job["work"]), "words.json"); jsave(out, p)
    print(f"words: {out['confirmadas_asr']}/{len(ref)} palavras com tempo do audio, {len(div)} divergencias -> {p}", flush=True)
    return out
