#!/usr/bin/env python3
"""Confere cada emenda NO ARQUIVO FINAL: transcreve ±4 s e mede o início da volta.

Uso (Python do mlx-whisper):
  ~/.local/share/uv/tools/mlx-whisper/bin/python conferir_emendas.py FINAL.mp4 ORIGINAL cortes.json

Para cada emenda imprime:
  - o texto em volta (frase anterior termina? a próxima começa inteira? sobrou
    "pode ir", "isso", "vai", "vamos lá", "ma…"?)
  - os primeiros 0,6 s depois da emenda em 20 ms: a voz ("V") deve aparecer em
    até ~0,1 s. "bbbbbbb" longo antes do V = respiração/suspiro que sobrou.
"""
import json, subprocess, sys

import numpy as np
import mlx_whisper

final, orig, cj = sys.argv[1:4]
cortes = sorted(json.load(open(cj)), key=lambda c: c[0])
keep, t = [], 0.0
for ini, fim in cortes:
    if ini > t:
        keep.append((t, ini))
    t = fim if fim is not None else float("inf")
keep.append((t, None))


def load(s, d):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, s):.3f}", "-t", str(d), "-i", final, "-vn",
                         "-f", "s16le", "-ac", "1", "-ar", "16000", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


acc = 0.0
for n, (x, y) in enumerate(keep[:-1], 1):
    acc += y - x
    au = load(acc - 4, 8)
    txt = mlx_whisper.transcribe(au, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="pt",
                                 condition_on_previous_text=False)["text"].strip()
    z = au[4 * 16000:int(4.6 * 16000)]
    tags = ""
    for i in range(0, len(z) - 320, 320):
        w = z[i:i + 320]
        db = 20 * np.log10(np.sqrt(np.mean(w ** 2)) + 1e-9)
        w0 = w - w.mean()
        ac = np.correlate(w0, w0, "full")[319:]
        v = ac[40:200].max() / (ac[0] + 1e-9) if ac[0] > 0 else 0
        tags += "V" if (db > -35 and v > 0.5) else ("b" if db > -45 else ".")
    print(f"E{n} {int(acc // 60)}:{acc % 60:05.2f} | {tags} | {txt}")
