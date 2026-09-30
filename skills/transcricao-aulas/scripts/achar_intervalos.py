#!/usr/bin/env python3
"""Acha intervalos (café, almoço, troca de bloco) numa gravação longa sem transcrever tudo.

Uso: python3 achar_intervalos.py GRAVACAO [--min 3] [--limiar -40] [--inicio-timeline 01:00:00:00] [--fps 30]
     [--janelas]   transcreve 60 s antes e depois de cada intervalo (um de cada vez, modelo leve)

Quando o usuário só quer "saber onde tem pausa", ele quer a lista rápido: rodar o Whisper em
9 h de áudio levou horas e comeu os 16 GB de RAM (nutrição módulo 4, set/2026). Aqui:
1. uma passada de silencedetect na gravação inteira (minutos, pouca memória);
2. junta silêncios separados por menos de 20 s de ruído (gente conversando longe do microfone);
3. lista cada intervalo >= --min minutos com o tempo da gravação e, se passado
   --inicio-timeline, o timecode para colar no DaVinci (soma o início da timeline);
4. --janelas: transcreve só 1 min de cada lado para confirmar "vamos para o intervalo" / "voltando".
"""
import argparse, re, subprocess, tempfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("gravacao")
ap.add_argument("--min", type=float, default=3.0, help="duração mínima do intervalo, em minutos")
ap.add_argument("--limiar", type=float, default=-40.0, help="dB abaixo do qual é silêncio")
ap.add_argument("--inicio-timeline", default="", help="timecode do início da timeline no DaVinci, ex. 01:00:00:00")
ap.add_argument("--fps", type=float, default=30.0)
ap.add_argument("--janelas", action="store_true")
a = ap.parse_args()


def hms(t):
    h, r = divmod(max(t, 0), 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def tc(t):
    base = 0.0
    if a.inicio_timeline:
        h, m, s, f = map(int, a.inicio_timeline.split(":"))
        base = h * 3600 + m * 60 + s + f / a.fps
    t += base
    fr = int(round((t - int(t)) * a.fps)) % int(a.fps)
    return f"{hms(t)}:{fr:02d}"


r = subprocess.run(["ffmpeg", "-nostats", "-i", a.gravacao, "-vn", "-af",
                    f"aresample=8000,silencedetect=n={a.limiar}dB:d=10", "-f", "null", "-"],
                   capture_output=True, text=True).stderr
ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", a.gravacao],
                           capture_output=True, text=True).stdout)
sil = list(zip(ini, fim + [dur] * (len(ini) - len(fim))))
junto = []
for x, y in sil:
    if junto and x - junto[-1][1] < 20:
        junto[-1][1] = y
    else:
        junto.append([x, y])
intervalos = [(x, y) for x, y in junto if y - x >= a.min * 60]
print(f"gravação: {hms(dur)} | {len(intervalos)} intervalo(s) de {a.min:g} min ou mais")
for n, (x, y) in enumerate(intervalos, 1):
    extra = f" | DaVinci {tc(x)} -> {tc(y)}" if a.inicio_timeline else ""
    print(f"{n}. {hms(x)} -> {hms(y)}  ({(y - x)/60:.0f} min){extra}")
if a.janelas and intervalos:
    import mlx_whisper  # rode com o python do mlx-whisper
    for n, (x, y) in enumerate(intervalos, 1):
        for rotulo, t0 in (("antes", max(0, x - 60)), ("depois", y)):
            with tempfile.NamedTemporaryFile(suffix=".wav") as w:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-t", "60", "-i", a.gravacao,
                                "-vn", "-ac", "1", "-ar", "16000", w.name], check=True)
                txt = mlx_whisper.transcribe(w.name, path_or_hf_repo="mlx-community/whisper-small-mlx",
                                             language="pt", verbose=None)["text"].strip()
            print(f"   {n} {rotulo} ({hms(t0)}): {txt[:220]}")
