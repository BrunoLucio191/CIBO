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


def scan_master(master, fps=3, top=48):
    """Whole-episode search for GENUINE smiles (strict smile cascade + visible teeth
    + both eyes open). Inside a cut the guest is often in profile or mid-word; the
    covers the client approved came from these moments (ep4: Larissa 17:48, 60:34;
    Juliana's intro and a 3/4 soft smile at 37:14). Writes <work>/master_smiles.jpg
    labelled n:t:x0 -> use as cover_from {"src": master, "t": t, "x0": x0}."""
    W, H = 960, 540
    r = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', master, '-vf', f'fps={fps},scale={W}:{H}',
                          '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], stdout=subprocess.PIPE)
    b = cv2.data.haarcascades
    face = cv2.CascadeClassifier(b + 'haarcascade_frontalface_default.xml')
    eye = cv2.CascadeClassifier(b + 'haarcascade_eye_tree_eyeglasses.xml')
    smile = cv2.CascadeClassifier(b + 'haarcascade_smile.xml')
    rows = []; i = 0
    while True:
        buf = r.stdout.read(W * H * 3)
        if len(buf) < W * H * 3: break
        img = np.frombuffer(buf, np.uint8).reshape(H, W, 3); t = round(i / fps, 2); i += 1
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        for (x, y, w, h) in face.detectMultiScale(g, 1.1, 7, minSize=(85, 85)):
            roi = g[y:y + h, x:x + w]
            if len(eye.detectMultiScale(roi[:h // 2], 1.1, 6, minSize=(w // 10, w // 10))) < 2: continue
            st = smile.detectMultiScale(roi[h // 2:], 1.4, 35, minSize=(w // 3, h // 9))
            if len(st) == 0: continue
            m = hsv[y + int(h * .66):y + int(h * .86), x + int(w * .3):x + int(w * .7)]
            teeth = float(((m[..., 2] > 170) & (m[..., 1] < 70)).mean()) if m.size else 0
            sharp = float(cv2.Laplacian(roi, cv2.CV_64F).var())
            rows.append(dict(t=t, cx=float((x + w / 2) * 2), fy=int(y * 2), s=float(max(s[2] for s in st) / w + 3 * teeth + min(sharp, 300) / 600)))
    rows.sort(key=lambda r: -r['s']); pick = []
    for r0 in rows:
        if all(abs(r0['t'] - p['t']) >= 1.2 for p in pick): pick.append(r0)
        if len(pick) == top: break
    pick.sort(key=lambda r: r['t']); tiles = []
    for n, p in enumerate(pick):
        fr = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(p['t']), '-i', master, '-frames:v', '1',
                             '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True).stdout
        im = np.frombuffer(fr, np.uint8).reshape(1080, 1920, 3)
        x0 = int(min(1920 - 608, max(0, p['cx'] - 304))); p['x0'] = x0
        y0 = int(max(0, min(1080 - 700, p['fy'] - 160)))
        tl = cv2.resize(im[y0:y0 + 700, x0:x0 + 608], (174, 200))
        cv2.putText(tl, f"{n}:{p['t']}:{x0}", (3, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1); tiles.append(tl)
    while len(tiles) % 10: tiles.append(np.zeros((200, 174, 3), np.uint8))
    cv2.imwrite(os.path.join(B, 'master_smiles.jpg'), np.vstack([np.hstack(tiles[i:i + 10]) for i in range(0, len(tiles), 10)]))
    json.dump(pick, open(os.path.join(B, 'master_smiles.json'), 'w'), indent=1)
    print('candidatos:', len(pick), '->', os.path.join(B, 'master_smiles.jpg'))

if __name__ == '__main__':
    if '--master' in sys.argv:
        scan_master(sys.argv[sys.argv.index('--master') + 1])
    else:
        for k in (sys.argv[1:] or list(JOB['clips'])): score_clip(k)
