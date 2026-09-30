#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Linha do queixo quadro a quadro no camera.mov (ja com enquadramento, zoom, push e respiro).

Uso: python3 chin_track.py job.json [--fps 10] [--sheet qa.jpg]
Saida: <work>/chin_track.json  {"fps", "t": [...], "chin": [...], "face_h": [...]}  (px no quadro 4K)

Mede no video da camera, e nao na fonte, para que a altura da legenda enxergue o auge de cada zoom: o zoom de 14%
desce o queixo na tela, e a legenda nunca pode encostar nele no meio do movimento (regra do usuario).
Queixo = o mais baixo entre a borda de baixo da caixa do YuNet e boca + 0,75 x (boca - olhos): a caixa as vezes
para na boca quando ela vira o rosto. Quadro sem deteccao = vizinho mais proximo (mao na frente, perfil).
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("--fps", type=float, default=10.0); ap.add_argument("--sheet")
a = ap.parse_args()
job = json.load(open(a.job))
W, H, DW, DH = 2160, 3840, 540, 960; S = W / DW
MODEL = str(Path.home() / ".cache/yunet/face_detection_yunet_2023mar.onnx")
det = cv2.FaceDetectorYN.create(MODEL, "", (DW, DH), 0.6, 0.3, 5000)
cam = os.path.join(job["work"], "camera.mov")

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", cam, "-vf", f"fps={a.fps},scale={DW}:{DH}", "-f", "rawvideo",
                      "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
n = len(raw) // (DW * DH * 3)
F = np.frombuffer(raw[:n * DW * DH * 3], np.uint8).reshape(n, DH, DW, 3)
T, C, FH, hits = [], [], [], []
# o camera.mov ja traz as referencias (card, tela dividida, tela cheia, cartao final): ali nao e o rosto dela
# (a testa do stock virava "queixo" em 3293 px); esses quadros herdam o vizinho mais proximo fora da referencia
REFS = [(r["start"], r["end"]) for r in job.get("malu_refs", [])]
for i, img in enumerate(F):
    T.append(round(i / a.fps, 3))
    if any(s0 - 0.05 <= T[-1] < s1 + 0.05 for s0, s1 in REFS):
        C.append(None); FH.append(None); continue
    _, f = det.detect(img)
    if f is None or not len(f):
        C.append(None); FH.append(None); continue
    f = max(f, key=lambda r: r[2] * r[3])
    x, y, w, h = f[:4]; lm = f[4:14].reshape(5, 2)
    eye, mouth = lm[:2, 1].mean(), lm[3:5, 1].mean()
    C.append(float(max(y + h, mouth + 0.75 * (mouth - eye)) * S)); FH.append(float(h * S)); hits.append(i)
if not hits: sys.exit("chin_track: nenhum rosto no camera.mov")
# falso rosto (mao, copo) num quadro isolado: queixo que foge da mediana dos vizinhos em mais de 0,6 altura de rosto
# e descartado (no reel 02 um quadro deu 3211 px contra ~1720 do plano e empurrou a legenda para a zona segura)
out = []
for i in hits:
    nb = [C[j] for j in hits if j != i and abs(j - i) <= 5]
    fh = [FH[j] for j in hits if abs(j - i) <= 5]
    if len(nb) >= 3 and abs(C[i] - float(np.median(nb))) > 0.6 * float(np.median(fh)):
        out.append(i)
for i in out:
    C[i] = FH[i] = None
hits = [i for i in hits if i not in out]
if out: print(f"chin_track: {len(out)} quadro(s) com falso rosto descartado(s): " + ", ".join(f"{T[i]:.1f}s" for i in out))
for i in range(n):
    if C[i] is None:
        j = min(hits, key=lambda k: abs(k - i)); C[i], FH[i] = C[j], FH[j]
out = os.path.join(job["work"], "chin_track.json")
json.dump(dict(fps=a.fps, t=T, chin=[round(c, 1) for c in C], face_h=[round(h, 1) for h in FH],
               detected=len(hits), frames=n), open(out, "w"))
print(f"chin_track: {len(hits)}/{n} quadros com rosto, queixo entre {min(C):.0f} e {max(C):.0f} px -> {out}")
if a.sheet:                                           # conferencia visual: linha do queixo desenhada
    idx = np.linspace(0, n - 1, 12).astype(int); tiles = []
    for i in idx:
        im = F[i].copy(); yy = int(C[i] / S)
        cv2.line(im, (0, yy), (DW, yy), (0, 255, 255), 2)
        cv2.putText(im, f"{T[i]:.1f}s", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        tiles.append(cv2.resize(im, (270, 480)))
    cv2.imwrite(a.sheet, np.vstack([np.hstack(tiles[r:r + 6]) for r in (0, 6)]))
    print("folha:", a.sheet)
