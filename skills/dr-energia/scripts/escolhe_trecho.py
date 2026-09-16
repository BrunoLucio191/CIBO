#!/usr/bin/env python3
"""Escolhe em que ponto da trilha entrar, em vez de sempre comecar em 0:00.

Procura um trecho da duracao do corte que ja esteja com a textura estabelecida
(fora da intro rarefeita), com energia estavel e uma leve subida ao longo do
trecho, para o corte terminar em alta em vez de no meio de um climax.

Uso: escolhe_trecho.py <faixa.mp3> <duracao_do_corte>
"""
import subprocess
import sys
import wave
import tempfile
import os

import numpy as np

JANELA = 1.0     # s por bloco de RMS


def envelope(caminho):
    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", caminho,
                    "-ac", "1", "-ar", "8000", tmp], check=True)
    with wave.open(tmp) as w:
        n = w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
        sr = w.getframerate()
    os.remove(tmp)
    passo = int(sr * JANELA)
    blocos = [x[i:i + passo] for i in range(0, len(x) - passo, passo)]
    rms = np.array([float(np.sqrt(np.mean(b ** 2)) + 1e-9) for b in blocos])
    return rms, len(x) / sr


def main():
    faixa, dur = sys.argv[1], float(sys.argv[2])
    rms, total = envelope(faixa)
    n = int(round(dur / JANELA))
    if total <= dur + 2:
        print(0.0); return

    pico = float(np.percentile(rms, 95))
    melhor, melhor_pt = 0.0, -1e9
    for i in range(0, len(rms) - n):
        jan = rms[i:i + n]
        med = float(jan.mean())
        # textura ja estabelecida: nao entra na intro quase muda
        if med < 0.35 * pico:
            continue
        estabilidade = 1.0 - min(float(jan.std()) / (med + 1e-9), 1.0)
        # leve crescimento do inicio ao fim do trecho
        metade = n // 2
        subida = (jan[metade:].mean() - jan[:metade].mean()) / (med + 1e-9)
        subida_pt = 1.0 - min(abs(subida - 0.10) / 0.35, 1.0)
        # nao estourar no trecho mais alto da faixa
        folga = 1.0 - min(max(med - 0.85 * pico, 0) / (0.3 * pico), 1.0)
        pt = estabilidade * 0.45 + subida_pt * 0.35 + folga * 0.20
        if pt > melhor_pt:
            melhor_pt, melhor = pt, i * JANELA
    print(f"{melhor:.1f}")


if __name__ == "__main__":
    main()
