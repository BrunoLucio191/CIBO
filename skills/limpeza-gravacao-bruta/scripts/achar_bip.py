#!/usr/bin/env python3
"""Acha bip/tom de claquete (tom puro, tipicamente 1–5 kHz) num intervalo do original.

Uso:
  python3 achar_bip.py VIDEO_OU_WAV INICIO DURACAO

Imprime, a cada 20 ms, frequência de pico e "tonalidade" (pico/média do espectro).
Bip = tonalidade alta (> ~35; o 1º toque passa de 100) numa frequência fixa acima de 2 kHz por 100 ms ou mais;
fala tem pico < 1,5 kHz e muda de frequência. No Pod Acontecer o bip é ~4,1 kHz,
toca duas vezes e o segundo encosta no "Fala, meus amigos": a volta tem que ser
no início do "F", não no tempo do Whisper.
"""
import subprocess, sys

import numpy as np

src, s, d = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s), "-t", str(d), "-i", src, "-vn",
                      "-f", "s16le", "-ac", "1", "-ar", "48000", "-"], capture_output=True).stdout
a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
fr = 960
ult_bip = None
for i in range(0, len(a) - fr, fr):
    x = a[i:i + fr]
    sp = np.abs(np.fft.rfft(x * np.hanning(fr)))
    f = int(np.argmax(sp) * 48000 / fr)
    ton = sp.max() / (sp.mean() + 1e-9)
    db = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    bip = f > 2000 and ton > 35 and db > -45
    if bip:
        ult_bip = s + i / 48000
    print(f"{s + i / 48000:8.2f} {db:5.0f} dB  pico {f:5d} Hz  tonal {ton:4.0f} {'<< BIP' if bip else ''}")
if ult_bip is not None:
    print(f"\núltimo quadro de bip: {ult_bip:.2f} — a volta deve ser DEPOIS dele e do eco (confira as linhas seguintes)")
