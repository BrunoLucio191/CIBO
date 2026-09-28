# -*- coding: utf-8 -*-
"""Punch-in (zoom on the video) as Premiere keyframes with Easy Ease + a 360° shutter.

The zoom is a step track of LEVELS (100%, 105%, ...). Every change of level is one
keyframe pair: a ramp of `ramp` s on a cubic-bezier (Easy Ease = 0.33,0,0.67,1) that
starts and lands at rest and stops EXACTLY on the target — no spring, no overshoot
(a bezier with y outside [0, 1] is refused). Scale is interpolated in log space, so
the zoom speed reads as constant (100->105 and 105->100 feel symmetric).

Motion blur only for the zoom: a frame whose zoom is moving is the mean of N >= 16
subframes spread over the shutter interval centred on the frame time (360° = the
whole 1/fps). The picture of that frame is re-scaled N times; nothing is re-timed.
Frames at rest are one warp (or untouched bytes at 100%).

Works on the yuv420p planes directly (no RGB round trip = no colour-matrix drift);
chroma is scaled about its own sited centre (left-sited horizontally, H.264 default).

The old engine (render.impact_motion: zoompan + sin pulse) went up and straight back
down, and zoompan rounds its crop to whole pixels per frame: it read as a spring.
"""
import math, subprocess
import numpy as np
import cv2

DEFAULT = dict(ramp=0.40, bezier=[0.33, 0.0, 0.67, 1.0], subframes=16, shutter=360, min_hold=0.40, min_rest=0.30)


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2) as p -> eased p. Monotonic, ends exactly on 0/1."""
    if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
        raise ValueError('cubic-bezier: x1/x2 must be in [0, 1]')
    if not (0 <= y1 <= 1 and 0 <= y2 <= 1):
        raise ValueError('cubic-bezier: y outside [0, 1] overshoots — not allowed for the punch-in')
    cx = 3 * x1; bx = 3 * (x2 - x1) - cx; ax = 1 - cx - bx
    cy = 3 * y1; by = 3 * (y2 - y1) - cy; ay = 1 - cy - by
    X = lambda u: ((ax * u + bx) * u + cx) * u
    Y = lambda u: ((ay * u + by) * u + cy) * u

    def ease(p):
        if p <= 0: return 0.0
        if p >= 1: return 1.0
        lo, hi, u = 0.0, 1.0, p
        for _ in range(60):                      # bisection: x(u) is monotonic on [0, 1]
            if X(u) < p: lo = u
            else: hi = u
            u = (lo + hi) / 2
            if hi - lo < 1e-9: break
        return Y(u)
    return ease


def events(c, ramp, min_hold=0.0):
    """(start, hold_until, amount) for every zoom event of the clip, output time. Each
    event holds at least `min_hold` after landing: in-and-straight-out is a bounce."""
    ev = []
    for e in c.get('impact_pulses', []):
        e = e if isinstance(e, dict) else dict(t=float(e))
        t = float(e['t']); a = float(e.get('amount', 0.05))
        until = float(e['until']) if 'until' in e else t + float(e.get('duration', 1.0)) - ramp
        ev.append((t, max(until, t + ramp + min_hold), a))
    for e in c.get('long_moves', []):
        t = float(e['t']); a = float(e.get('amount', 0.045))
        ev.append((t, max(t + float(e.get('duration', 1.6)) - ramp, t + ramp + min_hold), a))
    return sorted(ev)


def transitions(ev, ramp, min_hold=0.15, min_rest=0.30):
    """Level changes [(time, log_level)]. Every ramp lands on its keyframe before the next
    starts (no reversal mid-move), and the zoom never dips out and straight back in:
    a return must rest >= min_rest before the next rise, else it holds through (two
    destaques close together read as one punch, not as a bounce)."""
    pts = sorted({x for s, u, _ in ev for x in (s, u)})
    T, cur = [], 0.0
    for t in pts:
        lvl = max([a for s, u, a in ev if s <= t < u] or [0.0])
        if abs(lvl - cur) > 1e-9: T.append([t, lvl]); cur = lvl
    changed = True
    while changed:
        changed = False
        for i in range(len(T) - 1):
            prev = T[i - 1][1] if i else 0.0
            gap = T[i + 1][0] - T[i][0]
            if T[i][1] < prev and T[i + 1][1] > T[i][1] and gap < ramp + min_rest - 1e-6:
                new_t = T[i + 1][0] - ramp - min_rest       # return earlier, if the hold allows
                if i and new_t - T[i - 1][0] >= ramp + min_hold: T[i][0] = new_t
                else: del T[i]                              # else stay zoomed through
                changed = True; break
            same_way = (T[i][1] - prev) * (T[i + 1][1] - T[i][1]) > 0
            if gap < ramp - 1e-6 or (same_way and gap < ramp + min_hold - 1e-6):
                # overlapping ramps, or a stair (103% for a blink, then 105%): one ramp
                T[i][1] = T[i + 1][1]; del T[i + 1]; changed = True; break
        # drop no-op keyframes (same level as before)
        U = []
        for t, lv in T:
            if abs(lv - (U[-1][1] if U else 0.0)) > 1e-9: U.append([t, lv])
        if len(U) != len(T): changed = True
        T = U
    return [(t, math.log1p(a)) for t, a in T]


class Track:
    def __init__(self, c):
        P = dict(DEFAULT, **(c.get('punch') or {}))
        self.ramp = float(P['ramp']); self.ease = bezier(*P['bezier'])
        self.n = max(16, int(P['subframes'])); self.shutter = float(P['shutter']) / 360.0
        mh = float(P['min_hold'])
        self.T = transitions(events(c, self.ramp, mh), self.ramp, min_hold=mh, min_rest=float(P['min_rest']))

    def scale(self, t):
        v_from, v = 0.0, 0.0
        for tk, lv in self.T:
            if tk > t: break
            v_from, v = v, lv
            t_last = tk
        if v == v_from: return 1.0
        p = (t - t_last) / self.ramp
        return math.exp(v_from + (v - v_from) * self.ease(p))  # log-space interpolation

    def moving(self, a, b):
        return any(tk < b and tk + self.ramp > a for tk, _ in self.T)


def _warp(plane, s, cx, cy):
    h, w = plane.shape
    M = np.float32([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]])
    return cv2.warpAffine(plane, M, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)


def run(decode_cmd, c, out, fps, W, H, encode='-c:v libx264 -preset ultrafast -crf 14', clean_t=None, clean_out=None):
    """decode_cmd: ffmpeg command up to (not including) its outputs, with the video
    label [vo] (yuv420p WxH) and audio label [ao]. clean_t/clean_out: also save the
    frame at clean_t BEFORE the zoom (1-frame lossless file) — the cover is grabbed
    from it, so a punch-in landing on cover_t never leaks zoom or blur into the capa."""
    tr = Track(c)
    aud = out + '.audio.m4a'; vid = out + '.video.mp4'
    dec = subprocess.Popen(f'{decode_cmd} -map "[vo]" -f rawvideo -pix_fmt yuv420p pipe:1 '
                           f'-map "[ao]" -c:a aac -b:a 192k "{aud}"', shell=True, stdout=subprocess.PIPE)
    enc = subprocess.Popen(f'ffmpeg -y -v error -f rawvideo -pix_fmt yuv420p -s {W}x{H} -r {fps} -i - '
                           f'{encode} -pix_fmt yuv420p "{vid}"', shell=True, stdin=subprocess.PIPE)
    ys, cs = W * H, (W // 2) * (H // 2); fsz = ys + 2 * cs
    centres = [((W - 1) / 2, (H - 1) / 2), ((W - 1) / 4, (H - 2) / 4), ((W - 1) / 4, (H - 2) / 4)]
    half = 0.5 * tr.shutter / fps
    offs = [((k + 0.5) / tr.n - 0.5) * tr.shutter / fps for k in range(tr.n)]
    i = n_blur = 0
    clean_i = math.ceil(clean_t * fps - 1e-6) if clean_t is not None else -1   # what `ffmpeg -ss t` picks
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz: break
        if i == clean_i:
            subprocess.run(f'ffmpeg -y -v error -f rawvideo -pix_fmt yuv420p -s {W}x{H} -r {fps} -i - '
                           f'-frames:v 1 -c:v ffv1 "{clean_out}"', shell=True, input=buf, check=True)
        t = i / fps; i += 1
        if tr.moving(t - half, t + half):
            scales = [tr.scale(t + o) for o in offs]; n_blur += 1
        else:
            s = tr.scale(t)
            if abs(s - 1) < 1e-9: enc.stdin.write(buf); continue
            scales = [s]
        a = np.frombuffer(buf, np.uint8)
        planes = [a[:ys].reshape(H, W), a[ys:ys + cs].reshape(H // 2, W // 2), a[ys + cs:].reshape(H // 2, W // 2)]
        outp = []
        for pl, (cx, cy) in zip(planes, centres):
            f = pl.astype(np.float32); acc = np.zeros_like(f)
            for s in scales: acc += _warp(f, s, cx, cy)
            outp.append(np.clip(acc / len(scales) + 0.5, 0, 255).astype(np.uint8).ravel())
        enc.stdin.write(np.concatenate(outp).tobytes())
    enc.stdin.close(); enc.wait(); dec.wait()
    if dec.returncode or enc.returncode: raise SystemExit('punch: ffmpeg falhou')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', vid, '-i', aud, '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', out], check=True)
    import os; os.remove(vid); os.remove(aud)
    print(f'   punch-in: {len(tr.T)} keyframes, {n_blur} frames com motion blur ({tr.n} subframes)', flush=True)
