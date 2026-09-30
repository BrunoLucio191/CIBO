#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trilha de SFX e cama de musica da Malu (o render.py chama no prep quando job["sfx_engine"] = "malu").

Uso: python3 audio.py job.json   -> <work>/sfx_track.wav e <work>/music_bed.wav

SFX (job["sfx_events"], tempo editado): {"t", "sfx": nome em assets/sfx sem .wav, "db", "at": "peak"|"start"}
- "peak": o pico do arquivo cai em t (whoosh no ponto mais rapido do movimento); "start": o ataque cai em t.
- Regra do usuario: SFX nunca por cima de consoante. O pico e deslocado ate +-0,12 s para onde a fala tem menos
  energia em 3-8 kHz (fricativas e oclusivas); o deslocamento fica no relatorio.
- Nunca o mesmo arquivo duas vezes seguidas (confere e para).
Musica (job["music_source"]): {"file", "end": fim musical real em s, "gain_to_voice": -20, "hook": [ate_s, +dB],
"outro": [de_s, +dB]} -> cama ja cortada (fim natural da faixa = fim do reel), 20 dB abaixo da voz, com crescendo
no gancho e no cartao final. O job aponta music.file para a cama, offset 0, db 0; o render.py faz o ducking.
"""
import json, os, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); SKILL = os.path.dirname(HERE)
job = json.load(open(sys.argv[1]))
sys.path.insert(0, job.get("engine_scripts_fernanda", os.path.expanduser("~/.claude/skills/fernanda-produto/scripts")))
from timeline import segments, duration

SR = 48000; W = job["work"]; D = duration(job); LIB = os.path.join(SKILL, "assets", "sfx")


def load(path, sr=SR, ch=2):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", str(ch), "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, ch).copy()


def lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    return float(r.split("Summary:")[1].split("I:")[1].split("LUFS")[0])


# voz editada (mesmos trechos do render) -> envelope de consoantes (3-8 kHz) a cada 10 ms
voice = np.concatenate([load(job["src"], 16000, 1)[int(a * 16000):int(b * 16000), 0] for a, b in segments(job)])
h = 160; n = len(voice) // h
S = np.abs(np.fft.rfft(voice[:n * h].reshape(n, h) * np.hanning(h), axis=1)) ** 2
fr = np.fft.rfftfreq(h, 1 / 16000)
hf = 10 * np.log10(S[:, (fr >= 3000) & (fr <= 8000)].sum(1) + 1e-12)


def best_shift(t):
    """Deslocamento (s) em +-0,12 que poe o pico do SFX onde a fala tem menos consoante."""
    cand = np.arange(-12, 13); i0 = int(t * 100)
    score = [hf[max(0, i0 + c - 2):i0 + c + 3].max() if 0 <= i0 + c < n else -99 for c in cand]
    base = score[12]
    j = int(np.argmin(np.array(score) + np.abs(cand) * 0.15))            # prefere nao mexer se nao houver ganho
    return (cand[j] / 100.0, round(float(base), 1), round(float(score[j]), 1)) if score[j] < base - 3 else (0.0, base, base)


track = np.zeros((int((D + 1) * SR), 2), np.float32); rep = []; last = None
for ev in sorted(job.get("sfx_events", []), key=lambda e: e["t"]):
    if ev["sfx"] == last and not ev.get("src"): sys.exit(f"audio: {ev['sfx']} duas vezes seguidas")
    last = ev["sfx"]
    if ev.get("src"):                                   # trecho de outro arquivo (som do film burn, sincronizado com a luz)
        x = load(ev["src"])[int(ev["ss"] * SR):int((ev["ss"] + ev["dur"]) * SR)]
        fi = int(0.03 * SR); x[:fi] *= np.linspace(0, 1, fi)[:, None]
    else:
        x = load(os.path.join(LIB, ev["sfx"] + ".wav"))
    env = np.abs(x).max(1); pk = int(np.argmax(np.convolve(env, np.ones(480) / 480, mode="same")))
    on = int(np.argmax(env > env.max() * 0.03))
    ax = 0 if ev.get("at") == "raw" else (pk if ev.get("at", "peak") == "peak" else on)   # raw: o trecho comeca em t
    sh, hf0, hf1 = best_shift(ev["t"]) if ev.get("dodge", True) else (0.0, None, None)
    if ev.get("trim_before"):                                            # riser: so os ultimos N s antes do pico
        cut = max(0, ax - int(ev["trim_before"] * SR)); x = x[cut:]; ax -= cut
        fi = min(len(x), int(0.25 * SR)); x[:fi] *= np.linspace(0, 1, fi)[:, None]
    if ev.get("cut_after_peak") is not None:                             # termina logo depois do pico
        x = x[:ax + int(ev["cut_after_peak"] * SR)]
    start = int((ev["t"] + sh) * SR) - ax
    g = 10 ** (ev.get("db", -10) / 20)
    fo = min(len(x), int(0.03 * SR)); x[-fo:] *= np.linspace(1, 0, fo)[:, None]
    a0, a1 = max(0, start), min(len(track), start + len(x))
    if a1 > a0: track[a0:a1] += x[a0 - start:a1 - start] * g
    rep.append(dict(t=ev["t"], sfx=ev["sfx"], deslocado_s=round(sh, 2), consoante_antes_db=hf0, consoante_depois_db=hf1))
track = track[:int(D * SR)]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_s16le",
                os.path.join(W, "sfx_track.wav")], input=np.clip(track, -1, 1).tobytes(), check=True)
print(f"sfx_track.wav: {len(rep)} SFX em {D:.1f} s (1 a cada {D / max(1, len(rep)):.1f} s)")
for r in rep:
    if r["deslocado_s"]: print(f"   {r['sfx']} em {r['t']:.2f}s deslocado {r['deslocado_s']:+.2f}s para sair da consoante "
                               f"({r['consoante_antes_db']} -> {r['consoante_depois_db']} dB)")

ms = job.get("music_source")
if ms:
    off = max(0.0, float(ms["end"]) - D)
    bed = load(ms["file"])[int(off * SR):int((off + D) * SR)]
    tt = np.arange(len(bed)) / SR
    gdb = np.zeros(len(bed))
    hk, hdb = ms.get("hook", [3.5, 2.0]); ot, odb = ms.get("outro", [D - 3.0, 3.0])
    ramp = lambda x: 0.5 - 0.5 * np.cos(np.pi * np.clip(x, 0, 1))
    gdb += hdb * (1 - ramp((tt - (hk - 1.5)) / 1.5))                     # gancho: +2 dB que volta ate hk
    gdb += odb * ramp((tt - ot) / 1.2)                                   # cartao final: sobe junto com o fim da faixa
    bed = bed * (10 ** (gdb / 20))[:, None]
    fi = int(0.25 * SR); bed[:fi] *= np.linspace(0, 1, fi)[:, None]      # entrada curta
    tmp = os.path.join(W, "music_bed_raw.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", "-c:a", "pcm_f32le", tmp],
                   input=bed.astype(np.float32).tobytes(), check=True)
    vtmp = os.path.join(W, "voice_ref.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", "16000", "-ac", "1", "-i", "-", vtmp],
                   input=voice.astype(np.float32).tobytes(), check=True)
    lv, lb = lufs(vtmp), lufs(tmp); g = lv + float(ms.get("gain_to_voice", -20)) - lb
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", f"volume={g:.2f}dB", "-c:a", "pcm_s16le",
                    os.path.join(W, "music_bed.wav")], check=True)
    os.remove(tmp); os.remove(vtmp)
    print(f"music_bed.wav: {os.path.basename(ms['file'])} de {off:.1f}s a {off + D:.1f}s (fim natural {ms['end']}s), "
          f"voz {lv:.1f} LUFS, cama {lb:.1f} -> ganho {g:+.1f} dB (cama {ms.get('gain_to_voice', -20)} dB abaixo da voz)")
