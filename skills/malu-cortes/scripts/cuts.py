#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cortes de fala limpa a partir do envelope: pausas longas encurtadas e cortes de conteudo no silencio real.

Uso: python3 cuts.py AUDIO16K.wav IN OUT [--cut A B ...] [--keep-pause 0.25] [--min-pause 0.45] [--json saida.json]

- Pausa (< -40 dB, como o speech.py) maior que --min-pause vira ~--keep-pause (sobra metade de cada lado).
- --cut A B: trecho a remover (outra voz, "entendeu?", "ne?", falso comeco), em tempo do original. A borda e levada
  para o silencio mais proximo em ate 0,25 s (queda curta no meio de palavra e consoante, nao pausa: exige 60 ms).
- Saida: lista "cuts" pronta para o job (ordenada, sem sobreposicao) + relatorio das pausas encontradas.
"""
import argparse, json, subprocess
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("audio"); ap.add_argument("a", type=float); ap.add_argument("b", type=float)
ap.add_argument("--cut", nargs=2, type=float, action="append", default=[])
ap.add_argument("--keep-pause", type=float, default=0.25); ap.add_argument("--min-pause", type=float, default=0.45)
ap.add_argument("--thr", type=float, default=-40.0); ap.add_argument("--json")
a = ap.parse_args()
SR = 16000
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a.a - 1:.3f}", "-to", f"{a.b + 1:.3f}", "-i", a.audio,
                      "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True).stdout
y = np.frombuffer(raw, np.float32); h = SR // 100; n = len(y) // h; t0 = a.a - 1
env = 20 * np.log10(np.sqrt((y[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
sil = env < a.thr
T = lambda i: round(t0 + i / 100, 3)
I = lambda t: int(round((t - t0) * 100))

# silencios continuos (>= 60 ms) dentro da janela
runs, i = [], I(a.a)
while i < I(a.b):
    if sil[i]:
        j = i
        while j < I(a.b) and sil[j]: j += 1
        if j - i >= 6: runs.append((i, j))
        i = j
    else:
        i += 1


def snap(t, direction):
    """Leva t para dentro do silencio mais proximo (ate 0,25 s): inicio de corte vai para o comeco do silencio que
    segue a palavra mantida; fim de corte vai para o fim do silencio antes da proxima palavra mantida."""
    best = None
    for s, e in runs:
        if s / 100 + t0 - 0.25 <= t <= e / 100 + t0 + 0.25:
            c = T(min(e, s + 12)) if direction == "start" else T(max(s, e - 12))
            if best is None or abs(c - t) < abs(best - t): best = c
    return best if best is not None else t


cuts, rep = [], []
for s, e in runs:                                    # pausas longas -> ~keep_pause
    d = (e - s) / 100
    if d > a.min_pause and s > I(a.a) + 5 and e < I(a.b) - 5:
        k = int(a.keep_pause * 50)
        cuts.append([T(s + k), T(e - k)]); rep.append(dict(pausa=[T(s), T(e)], dur=round(d, 2)))
for c0, c1 in a.cut:                                  # cortes de conteudo no silencio
    cuts.append([snap(c0, "start"), snap(c1, "end")])
cuts.sort(); out = []
for c in cuts:
    if out and c[0] <= out[-1][1] + 0.05: out[-1][1] = max(out[-1][1], c[1])
    else: out.append(c)
kept = sum(e - s for s, e in zip([a.a] + [c[1] for c in out], [c[0] for c in out] + [a.b]))
res = dict(inicio=a.a, fim=a.b, cuts=[[round(x, 3), round(y_, 3)] for x, y_ in out], pausas_encurtadas=rep, fala_mantida_s=round(kept, 2))
print(json.dumps(res, ensure_ascii=False))
if a.json: json.dump(res, open(a.json, "w"), ensure_ascii=False, indent=1)
