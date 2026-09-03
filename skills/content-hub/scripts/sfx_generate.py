#!/usr/bin/env python3
"""Generate the original, client-owned Content Hub micro-SFX pack."""
import os
import wave

import numpy as np


SR = 48000


def write(path, signal):
    signal = np.clip(signal, -1, 1)
    stereo = np.stack([signal, signal], axis=1)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes((stereo * 32767).astype("<i2").tobytes())


def click():
    n = int(0.065 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(17)
    noise = rng.standard_normal(n)
    impulse = noise * np.exp(-t * 105)
    tone = np.sin(2 * np.pi * 1450 * t) * np.exp(-t * 125)
    out = impulse * 0.75 + tone * 0.25
    out /= np.max(np.abs(out)) + 1e-9
    out *= 0.12
    out[:24] *= np.linspace(0, 1, 24)
    out[-220:] *= np.linspace(1, 0, 220)
    return out.astype(np.float32)


def whoosh():
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(29)
    noise = rng.standard_normal(n)
    smooth = np.zeros(n)
    state = 0.0
    for i, value in enumerate(noise):
        alpha = 0.035 + 0.18 * (i / max(1, n - 1))
        state += alpha * (value - state)
        smooth[i] = state
    env = np.sin(np.pi * np.clip(t / t[-1], 0, 1)) ** 1.7
    out = smooth * env
    out /= np.max(np.abs(out)) + 1e-9
    return (out * 0.085).astype(np.float32)


def pop():
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * (105 - 28 * t / t[-1]) * t) * np.exp(-t * 26)
    tick = np.sin(2 * np.pi * 780 * t) * np.exp(-t * 90)
    out = 0.82 * tone + 0.18 * tick
    out /= np.max(np.abs(out)) + 1e-9
    return (out * 0.10).astype(np.float32)


def main():
    outdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
    os.makedirs(outdir, exist_ok=True)
    write(os.path.join(outdir, "click.wav"), click())
    write(os.path.join(outdir, "whoosh_soft.wav"), whoosh())
    write(os.path.join(outdir, "pop_low.wav"), pop())


if __name__ == "__main__":
    main()
