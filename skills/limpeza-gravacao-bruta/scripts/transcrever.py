#!/usr/bin/env python3
"""Transcreve a gravação bruta inteira e grava segmentos com tempo absoluto.

Uso (Python do mlx-whisper):
  ~/.local/share/uv/tools/mlx-whisper/bin/python transcrever.py VIDEO --out DIR [--rapido]

Saídas em DIR:
  audio16k.wav   — áudio mono 16 kHz do original (reusado pelos outros scripts)
  segmentos.tsv  — início<TAB>fim<TAB>texto, em segundos do ORIGINAL

--rapido: modelo tiny com áudio a 1,5x (~1 min para 1 h). Só serve para uma
triagem "teve pausa ou não?". Para decidir cortes, use o padrão (large-v3-turbo,
~5 min para 1 h em Apple Silicon).
"""
import argparse, os, subprocess, sys

import mlx_whisper

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--out", required=True)
ap.add_argument("--rapido", action="store_true")
ap.add_argument("--idioma", default="pt")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)

wav = os.path.join(a.out, "audio16k.wav")
if not os.path.exists(wav):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vn", "-ac", "1", "-ar", "16000", wav], check=True)

fonte, escala, modelo = wav, 1.0, "mlx-community/whisper-large-v3-turbo"
if a.rapido:
    fonte = os.path.join(a.out, "audio_rapido.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-af", "atempo=1.5", fonte], check=True)
    escala, modelo = 1.5, "mlx-community/whisper-tiny"

# condition_on_previous_text=False evita que uma alucinação ("tá tá tá…") contamine o resto
r = mlx_whisper.transcribe(fonte, path_or_hf_repo=modelo, language=a.idioma,
                           condition_on_previous_text=False)
nome = "segmentos_rapido.tsv" if a.rapido else "segmentos.tsv"
with open(os.path.join(a.out, nome), "w") as f:
    for s in r["segments"]:
        f.write(f"{s['start']*escala:.2f}\t{s['end']*escala:.2f}\t{s['text'].strip()}\n")
print(f"ok: {len(r['segments'])} segmentos -> {os.path.join(a.out, nome)}", file=sys.stderr)
