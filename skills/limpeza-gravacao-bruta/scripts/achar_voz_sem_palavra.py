#!/usr/bin/env python3
"""Acha trechos com voz que nenhuma palavra da transcrição cobre: hesitação, gagueira, frase largada, risada.

Uso:
  python3 achar_voz_sem_palavra.py AUDIO16K.wav WHISPER.json [--min 0.4] [--limiar -30]

WHISPER.json = saída do mlx_whisper com --word-timestamps True (tempos no mesmo áudio).

Por que existe (Katia, 03/10): nem o large-v3 com prompt de hesitação escreveu o "ah, é… e aí" de 2 s
nem o "eu, eu, eu, eu" da convidada; a busca por texto ("é", "ahn") só devolveu o verbo "é". Energia de voz
(> limiar dB em janelas de 50 ms) sem palavra a ±0,15 s é o sinal. A lista mistura risada e reação: transcreva
cada candidato isolado com dois modelos (large-v3 e turbo) antes de decidir.
"""
import argparse, json, wave

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("wav")
ap.add_argument("json")
ap.add_argument("--min", type=float, default=0.4, help="duração mínima do trecho (s)")
ap.add_argument("--limiar", type=float, default=-30, help="dBFS acima do qual a janela conta como voz")
a = ap.parse_args()

W = [w for s in json.load(open(a.json))["segments"] for w in s.get("words", [])]
w = wave.open(a.wav)
sr = w.getframerate()
d = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
hop = sr // 20  # 50 ms
n = len(d) // hop
e = 20 * np.log10(np.sqrt((d[: n * hop].reshape(n, hop) ** 2).mean(1)) / 32768 + 1e-9)

cob = np.zeros(n, bool)
for x in W:
    cob[max(0, int(x["start"] * 20) - 3): int(x["end"] * 20) + 4] = True
v = (e > a.limiar) & ~cob


def f(t):
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def ctx(t):
    antes = [x["word"].strip() for x in W if t - 3 < x["end"] <= t][-5:]
    depois = [x["word"].strip() for x in W if t < x["start"] < t + 4][:5]
    return " ".join(antes) + "  ⟨?⟩  " + " ".join(depois)


i = 0
while i < n:
    if v[i]:
        j = i
        while j < n and v[j]:
            j += 1
        if (j - i) / 20 >= a.min:
            print(f"{f(i / 20)}  {(j - i) / 20:.2f}s  {e[i:j].mean():.0f} dB | {ctx(i / 20)}")
        i = j
    else:
        i += 1
