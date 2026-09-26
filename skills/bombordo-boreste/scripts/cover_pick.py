#!/usr/bin/env python3
"""Suggest cover frames: face toward camera, both eyes open, smiling, sharp.

  JOB=job.json python3 cover_pick.py [clip ...]     # writes <work>/cover_cands_<clip>.jpg + .json

A cover picked by hand at a round second tends to land mid-word (mouth
twisted), mid-blink or on a profile. This scores every 0.2 s of the cut
(A_<clip>.mp4, i.e. exactly what cover.py grabs) and tiles the best distinct
candidates, labelled with their cover_t, for a human to choose from.
"""
import os, sys, json, subprocess
import numpy as np, cv2

JOB = json.load(open(os.environ['JOB'])); B = os.environ.get('WORK', JOB.get('work', './work'))
STEP = 0.2; SW, SH = 540, 960

def frames(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={1/STEP},scale={SW}:{SH}',
                        '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True).stdout
    n = len(r) // (SW * SH * 3)
    return np.frombuffer(r[:n * SW * SH * 3], np.uint8).reshape(n, SH, SW, 3)

def score_clip(k):
    base = cv2.data.haarcascades
    face = cv2.CascadeClassifier(base + 'haarcascade_frontalface_default.xml')
    eye = cv2.CascadeClassifier(base + 'haarcascade_eye_tree_eyeglasses.xml')
    smile = cv2.CascadeClassifier(base + 'haarcascade_smile.xml')
    F = frames(os.path.join(B, f'A_{k}.mp4'))
    rows = []
    for i, img in enumerate(F):
        t = round(i * STEP, 2)
        if t < 1.0: continue
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        fs = [f for f in face.detectMultiScale(g, 1.1, 7, minSize=(110, 110)) if f[1] + f[3] / 2 < SH * 0.5]
        if not fs: continue
        x, y, w, h = max(fs, key=lambda f: f[2])
        roi = g[y:y + h, x:x + w]
        eyes = eye.detectMultiScale(roi[:h // 2], 1.1, 6, minSize=(w // 10, w // 10))
        sm = smile.detectMultiScale(roi[h // 2:], 1.6, 22, minSize=(w // 4, h // 10))
        sharp = cv2.Laplacian(roi, cv2.CV_64F).var()
        centred = 1 - abs((x + w / 2) - SW / 2) / (SW / 2)
        s = 2.0 * min(len(eyes), 2) + 1.5 * (len(sm) > 0) + min(sharp / 150, 2) + 1.5 * centred + w / 200
        rows.append(dict(t=t, score=round(float(s), 2), eyes=int(len(eyes)), smile=bool(len(sm)), sharp=round(float(sharp)), i=i))
    rows.sort(key=lambda r: -r['score'])
    pick = []
    for r in rows:
        if all(abs(r['t'] - p['t']) >= 2.0 for p in pick): pick.append(r)
        if len(pick) == 8: break
    tiles = []
    for p in pick:
        im = cv2.resize(F[p['i']], (270, 480))
        cv2.putText(im, f"t={p['t']}", (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        tiles.append(im)
    while len(tiles) < 8: tiles.append(np.zeros((480, 270, 3), np.uint8))
    sheet = np.vstack([np.hstack(tiles[:4]), np.hstack(tiles[4:])])
    cv2.imwrite(os.path.join(B, f'cover_cands_{k}.jpg'), sheet)
    json.dump([{kk: vv for kk, vv in p.items() if kk != 'i'} for p in pick],
              open(os.path.join(B, f'cover_cands_{k}.json'), 'w'), indent=1)
    print(k, [(p['t'], p['score']) for p in pick], flush=True)

if __name__ == '__main__':
    for k in (sys.argv[1:] or list(JOB['clips'])): score_clip(k)
