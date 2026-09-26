#!/usr/bin/env python3
"""Where can captions sit without covering a face?

Samples the cropped/zoomed cut (A_<clip>.mp4, 1080x1920) every STEP seconds,
detects faces (frontal + profile, OpenCV Haar) and estimates the chin line as
the bottom of the face box plus a margin (Haar boxes stop around the mouth).
Returns the caption centre (y in the 1920 frame) that keeps a two-line caption
block below the chin in ~all sampled frames, clamped to the Reels safe area.
"""
import os, sys, json, subprocess
import numpy as np

W, H = 1080, 1920
STEP = float(os.environ.get('SAFE_STEP', '0.4'))
CHIN = float(os.environ.get('SAFE_CHIN', '1.22'))     # chin ~= top + 1.25 * haar box height
HALF_BLOCK = 100                                        # half of a two-line caption block (px)
MARGIN = 36
Y_MIN, Y_MAX = 1180, 1480                               # never above the old default; stay clear of the Reels UI

def frames(path, step=STEP):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps=1/{step},scale=540:960,format=gray',
                        '-f', 'rawvideo', '-'], capture_output=True).stdout
    n = len(r) // (540 * 960)
    return np.frombuffer(r[:n * 540 * 960], dtype=np.uint8).reshape(n, 960, 540)

def chins(path):
    import cv2
    base = cv2.data.haarcascades
    fr = cv2.CascadeClassifier(os.path.join(base, 'haarcascade_frontalface_default.xml'))
    pr = cv2.CascadeClassifier(os.path.join(base, 'haarcascade_profileface.xml'))
    out = []
    for g in frames(path):
        faces = list(fr.detectMultiScale(g, 1.1, 6, minSize=(70, 70)))
        faces += list(pr.detectMultiScale(g, 1.1, 6, minSize=(70, 70)))
        faces += [(540 - x - w, y, w, h) for x, y, w, h in pr.detectMultiScale(cv2.flip(g, 1), 1.1, 6, minSize=(70, 70))]
        # a real speaker face in these close crops is big and in the upper half:
        # small boxes low in the frame are hands, shirts, glasses (false positives)
        faces = [(x, y, w, h) for x, y, w, h in faces if h >= 90 and y + h / 2 < 480]
        out.append(max(((y + h * CHIN) * 2 for x, y, w, h in faces), default=None))
    return out

def caption_cy(path):
    c = [v for v in chins(path) if v is not None]
    if not c:
        return Y_MIN + 120, dict(frames_with_face=0)
    p = float(np.percentile(c, 90))
    cy = int(min(Y_MAX, max(Y_MIN, p + MARGIN + HALF_BLOCK)))
    return cy, dict(frames_with_face=len(c), chin_p50=round(float(np.percentile(c, 50))), chin_p92=round(p), cap_cy=cy)

if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(p, caption_cy(p))
