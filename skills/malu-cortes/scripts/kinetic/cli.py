#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legenda palavra por palavra da Malu (adaptada do kinetic do Bombordo).

  python3 cli.py job.json words  [--force]   # 1. tempo por palavra      -> <work>/kinetic/words.json
  python3 cli.py job.json blocks [--force]   # 2. blocos + destaques     -> <work>/kinetic/blocks.json (editavel)
  python3 cli.py job.json chin               # 3. queixo no camera.mov   -> <work>/chin_track.json
  python3 cli.py job.json layer              # 4. camada sem perdas      -> <work>/kinetic_caps.mov + kinetic/positions.json
  python3 cli.py job.json all                # 1-4 (words/blocks so se nao existirem) — o render.py prep chama este
  python3 cli.py job.json sheet VIDEO SAIDA.jpg [--start T0] [--dur D]
      folha de contatos no meio de cada movimento: entrada, destaque e saida de legenda, entrada de zoom/push.
      VIDEO pode ser a previa (comeca em T0) ou o final.

Config: kinetic/config.json (padrao da Malu) + job["kinetic"] + <work>/kinetic.json.
Chaves do job: captions, word_timing (Whisper do audio editado), audio16k (master 16 kHz), keywords,
caption_layouts [{start, end, cy, kind}] (tempo editado; tela cheia, card), broll (tela dividida vira layout).
"""
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import load_config, kdir, jload, fern_path

args = sys.argv[1:]
JOBF = os.path.abspath(args[0]); cmd = args[1]; FORCE = "--force" in args
JOB = json.load(open(JOBF)); JOB["_path"] = JOBF
CFG = load_config(JOB); WORK = JOB["work"]; KD = kdir(WORK)
fern_path(JOB)
from timeline import duration, o


def opt(name, default):
    return float(args[args.index(name) + 1]) if name in args else default


def layouts():
    """Intervalos em que a legenda segue o layout, nao o queixo: tela dividida (referencias) e job caption_layouts."""
    L = []
    for b in JOB.get("broll", []):
        a, e = o(JOB, b["start"]), o(JOB, b["end"])
        if b.get("layout", "split") == "split":
            if L and abs(L[-1]["end"] - a) < 0.05 and L[-1]["kind"] == "tela dividida": L[-1]["end"] = e
            else: L.append(dict(start=a, end=e, cy=CFG["position"]["split_cy"], kind="tela dividida"))
    L += [dict(x) for x in JOB.get("caption_layouts", [])]
    return sorted(L, key=lambda x: x["start"])


def words():
    p = os.path.join(KD, "words.json")
    if FORCE or not os.path.exists(p) or cmd == "words":
        import align; align.build(JOB, CFG)


def blocks():
    p = os.path.join(KD, "blocks.json")
    if FORCE or not os.path.exists(p) or cmd == "blocks":
        import segment; segment.build(JOB, CFG)


def chin():
    cam, ct = os.path.join(WORK, "camera.mov"), os.path.join(WORK, "chin_track.json")
    if not os.path.exists(cam):
        print("   aviso: sem camera.mov (camera_engine desligado): legenda na altura padrao"); return None
    if cmd == "chin" or not os.path.exists(ct) or os.path.getmtime(ct) < os.path.getmtime(cam):
        subprocess.run([sys.executable, os.path.join(os.path.dirname(HERE), "chin_track.py"), JOBF,
                        "--sheet", os.path.join(KD, "chin_sheet.jpg")], check=True)
    return jload(ct)


def layer():
    import kinrender
    D = duration(JOB)
    ch = chin() or dict(t=[0.0, D], chin=[CFG["position"]["default_cy"] - 400] * 2, face_h=[0.0, 0.0])
    shots, acc = [], 0.0                        # planos em tempo editado (a altura so muda no corte)
    for s0, s1, _ in JOB.get("shots", []):
        shots.append((acc, acc + s1 - s0)); acc += s1 - s0
    rep, n = kinrender.render(jload(os.path.join(KD, "blocks.json")), CFG, D, ch, layouts(),
                              os.path.join(WORK, "kinetic_caps.mov"), shots or None, JOB.get("graphics", []), JOB)
    clamp = [r for r in rep if r.get("zona_segura_venceu")]
    print(f"camada: {n} quadros, {len(rep)} blocos -> {os.path.join(WORK, 'kinetic_caps.mov')}")
    for r in clamp:
        print(f"   ZONA SEGURA VENCEU no bloco {r['id']} ({r['t_in']}s) \"{r['texto']}\": "
              f"distancia ao queixo {r.get('distancia_do_queixo', '-')} px")
    for r in rep:
        if r.get("aviso_layout"): print(f"   aviso bloco {r['id']} ({r['t_in']}s): {r['aviso_layout']}")
    if not clamp: print("   nenhum bloco precisou ceder para a zona segura")


def sheet():
    import cv2, numpy as np, unicodedata, kinrender
    video, out = args[2], args[3]; t0 = opt("--start", 0.0); t1 = t0 + opt("--dur", 1e9)
    bl = [b for b in jload(os.path.join(KD, "blocks.json"))["blocks"] if b["words"]]
    kinrender.timeline(bl, CFG, 9999)
    mom = []
    for b in bl:
        txt = " ".join(w["w"] for w in b["words"])[:22]
        if b["kind"] == "highlight": mom += [(b["t_in"] + 0.10, f"destaque in {txt}"), (b["t_in"] + 0.35, f"destaque {txt}")]
        else: mom += [(b["t_in"] + 0.08, f"entrada {b['preset']}")]
        mom.append((b["t_out"] + b["exit_dur"] * 0.5, "saida"))
    for m in JOB.get("camera_moves", []):
        if m["kind"] == "punch": mom.append((m["t"] + m.get("in", 0.3) / 2, f"zoom meio {m['amount']:.2f}"))
        elif m["kind"] == "push": mom.append(((m["t"] + m["until"]) / 2, f"push meio {m['amount']:.2f}"))
    for g in JOB.get("graphics", []):
        mom.append((g["t"] + g.get("in", 0.4) / 2, f"grafico {g.get('name', '')}"))
    mom = sorted(m for m in mom if t0 <= m[0] <= t1)
    tiles = []
    for t, lab in mom:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t - t0:.3f}", "-i", video, "-frames:v", "1", "-vf",
                            "scale=270:480", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
        if len(r) < 270 * 480 * 3: continue
        im = np.frombuffer(r, np.uint8).reshape(480, 270, 3).copy()
        cv2.rectangle(im, (0, 0), (270, 34), (0, 0, 0), -1)
        cv2.putText(im, f"{t:.2f}s", (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        lab = "".join(c for c in unicodedata.normalize("NFD", lab) if unicodedata.category(c) != "Mn")
        cv2.putText(im, lab[:34], (4, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 255, 255), 1)
        tiles.append(im)
    while len(tiles) % 6: tiles.append(np.zeros((480, 270, 3), np.uint8))
    cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]))
    print(f"folha de contatos: {len(mom)} momentos -> {out}")


if cmd in ("words", "all"): words()
if cmd in ("blocks", "all"): blocks()
if cmd == "chin": chin()
if cmd in ("layer", "all"): layer()
if cmd == "sheet": sheet()
