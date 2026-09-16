#!/usr/bin/env python3
"""Shot-aware OpenCV face analysis for stable 9:16 podcast crops.

The result is a cropx_timeline suitable for job.json.  Detection is sampled,
but camera cuts are located at frame precision.  One robust median crop is used
per shot, avoiding the frame-by-frame "face hunting" that causes vibration.
"""
import argparse
import json
import math
import os

import cv2
import numpy as np


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def in_keep(t, keeps):
    return any(a <= t < b for a, b in keeps)


def detect_largest(frame, detector, prefer=None):
    """YuNet DNN detection (OpenCV 5 removed the Haar cascade classifiers)."""
    height, width = frame.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(frame)
    if faces is None:
        return None
    candidates = []
    for f in faces:
        x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
        # Podcast faces belong in the upper 78% and should not be tiny props.
        if y + h / 2 > height * 0.78:
            continue
        if w < max(24, width / 24):
            continue
        candidates.append((w * h, x + w / 2, y + h / 2, w, h))
    if not candidates:
        return None
    biggest = max(candidates, key=lambda z: z[0])
    if prefer in ('left', 'right'):
        # Two-shots put both people in frame; the guest we follow is always on
        # the same side, so pick that side among the plausibly-sized faces
        # instead of whichever head happens to be nearer the camera.
        plausible = [z for z in candidates if z[0] >= biggest[0] * 0.40]
        return (max(plausible, key=lambda z: z[1]) if prefer == 'right'
                else min(plausible, key=lambda z: z[1]))
    return biggest


def finalize(shots, start, end, xs, width, crop_width, fallback):
    if end - start < 1 / 60:
        return fallback
    if xs:
        face_x = float(np.median(xs))
        cropx = clamp((face_x - crop_width / 2) / (width - crop_width), 0.0, 1.0)
        confidence = len(xs)
    else:
        face_x = None
        cropx = fallback
        confidence = 0
    # Quantization plus one crop per camera shot prevents micro-jitter.
    cropx = round(cropx / 0.005) * 0.005
    shots.append(dict(start=round(start, 3), end=round(end, 3),
                      cropx=round(cropx, 3), face_x=face_x,
                      detections=confidence))
    return cropx


def analyse(src, keeps, crop_width=None, sample_every=5, scene_threshold=18.0,
            fallback=0.5, prefer=None):
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit(f'cannot open video: {src}')
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if not crop_width:
        # Derive the 9:16 window from the real source height so sub-1080p
        # masters are analysed at their native resolution.
        crop_width = int(round(height * 9 / 16)) // 2 * 2
    model = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'assets', 'yunet.onnx')
    detector = cv2.FaceDetectorYN.create(model, '', (320, 320), 0.55)
    shots = []
    current_fallback = fallback

    for keep_start, keep_end in keeps:
        cap.set(cv2.CAP_PROP_POS_MSEC, keep_start * 1000)
        start_frame = int(round(keep_start * fps))
        end_frame = int(round(keep_end * fps))
        shot_start = keep_start
        xs = []
        prev_small = None
        for frame_no in range(start_frame, end_frame):
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_no / fps
            small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
            small = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if prev_small is not None:
                score = float(cv2.absdiff(prev_small, small).mean())
                if score >= scene_threshold and t - shot_start >= 0.20:
                    current_fallback = finalize(
                        shots, shot_start, t, xs, width, crop_width, current_fallback)
                    shot_start, xs = t, []
            prev_small = small
            if (frame_no - start_frame) % sample_every == 0:
                detect_w = min(960, width)
                detect_h = round(height * detect_w / width)
                scaled = cv2.resize(frame, (detect_w, detect_h), interpolation=cv2.INTER_AREA)
                face = detect_largest(scaled, detector, prefer=prefer)
                if face:
                    xs.append(face[1] * width / detect_w)
        current_fallback = finalize(
            shots, shot_start, keep_end, xs, width, crop_width, current_fallback)
    cap.release()

    # Merge adjacent entries only when both the crop and source are continuous.
    merged = []
    for shot in shots:
        if (merged and abs(merged[-1]['end'] - shot['start']) < 1 / fps + 1e-3
                and abs(merged[-1]['cropx'] - shot['cropx']) <= 0.015):
            merged[-1]['end'] = shot['end']
            merged[-1]['detections'] += shot['detections']
        else:
            merged.append(shot)
    timeline = [[s['start'], s['cropx']] for s in merged]
    return dict(src=src, width=width, height=height, fps=fps,
                crop_width=crop_width, timeline=timeline, shots=merged)


def preview(result, out):
    cap = cv2.VideoCapture(result['src'])
    tiles = []
    for shot in result['shots']:
        t = (shot['start'] + shot['end']) / 2
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        cw = result['crop_width']
        x = round((result['width'] - cw) * shot['cropx'])
        crop = frame[:, x:x + cw]
        tile = cv2.resize(crop, (270, 480), interpolation=cv2.INTER_AREA)
        label = f"{shot['start']:.2f}s  x={shot['cropx']:.3f}  n={shot['detections']}"
        cv2.rectangle(tile, (0, 0), (270, 28), (0, 0, 0), -1)
        cv2.putText(tile, label, (7, 19), cv2.FONT_HERSHEY_SIMPLEX,
                    0.43, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(tile)
    cap.release()
    if not tiles:
        return
    cols = min(5, len(tiles)); rows = math.ceil(len(tiles) / cols)
    sheet = np.full((rows * 480, cols * 270, 3), 245, np.uint8)
    for i, tile in enumerate(tiles):
        sheet[(i // cols) * 480:(i // cols + 1) * 480,
              (i % cols) * 270:(i % cols + 1) * 270] = tile
    cv2.imwrite(out, sheet)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--clip', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--preview')
    ap.add_argument('--scene-threshold', type=float, default=18.0)
    ap.add_argument('--prefer', choices=['left', 'right'], default=None,
                    help='side of the frame where the tracked guest sits')
    args = ap.parse_args()
    job = json.load(open(args.job, encoding='utf-8'))
    clip = job['clips'][args.clip]
    src = os.path.join(job['srcdir'], clip['src'])
    result = analyse(src, clip['keeps'], scene_threshold=args.scene_threshold,
                     fallback=float(clip.get('cropx', 0.5)), prefer=args.prefer)
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    json.dump(result, open(args.out, 'w', encoding='utf-8'), indent=2)
    if args.preview:
        os.makedirs(os.path.dirname(args.preview) or '.', exist_ok=True)
        preview(result, args.preview)
    print(json.dumps(result['timeline']))


if __name__ == '__main__':
    main()
