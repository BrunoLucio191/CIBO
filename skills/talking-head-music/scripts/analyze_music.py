#!/usr/bin/env python3
"""Measure comparable technical descriptors for music candidates."""
import argparse
import json
import math
import os
import subprocess

import numpy as np


def run(command):
    return subprocess.run(command, check=True, capture_output=True)


def duration(path):
    return float(run([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=nw=1:nk=1', path,
    ]).stdout.decode().strip())


def decode(path, seconds=120.0, rate=22050):
    raw = run([
        'ffmpeg', '-v', 'error', '-t', str(seconds), '-i', path,
        '-ac', '1', '-ar', str(rate), '-f', 'f32le', '-'
    ]).stdout
    return np.frombuffer(raw, dtype=np.float32), rate


def loudness(path):
    proc = subprocess.run([
        'ffmpeg', '-nostats', '-hide_banner', '-i', path,
        '-af', 'loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json',
        '-f', 'null', '-'
    ], capture_output=True, text=True)
    text = proc.stderr
    start, end = text.rfind('{'), text.rfind('}')
    if start < 0 or end < start:
        return {}
    data = json.loads(text[start:end + 1])
    return {
        'integrated_lufs': float(data['input_i']),
        'true_peak_dbtp': float(data['input_tp']),
        'lra_lu': float(data['input_lra']),
    }


def descriptors(signal, rate):
    if signal.size < rate:
        return {}
    frame, hop = 2048, 512
    n = 1 + (signal.size - frame) // hop
    frames = np.lib.stride_tricks.as_strided(
        signal, shape=(n, frame), strides=(signal.strides[0] * hop, signal.strides[0]))
    windowed = frames * np.hanning(frame)
    rms = np.sqrt(np.mean(windowed * windowed, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    spectrum = np.abs(np.fft.rfft(windowed, axis=1))
    freqs = np.fft.rfftfreq(frame, 1 / rate)
    centroid = np.sum(spectrum * freqs, axis=1) / (np.sum(spectrum, axis=1) + 1e-12)

    onset = np.maximum(0, np.diff(rms, prepend=rms[0]))
    onset -= onset.mean()
    ac = np.correlate(onset, onset, mode='full')[len(onset) - 1:]
    lag_lo = max(1, round((60 / 180.0) * rate / hop))
    lag_hi = min(len(ac) - 1, round((60 / 60.0) * rate / hop))
    if lag_hi > lag_lo:
        lag = lag_lo + int(np.argmax(ac[lag_lo:lag_hi + 1]))
        bpm = 60 * rate / (hop * lag)
    else:
        bpm = 0.0

    peak = float(np.max(np.abs(signal)))
    active = db[db > np.percentile(db, 10)]
    return {
        'estimated_bpm': round(float(bpm), 1),
        'brightness_centroid_hz': round(float(np.median(centroid)), 1),
        'dynamic_range_db': round(float(np.percentile(active, 90) - np.percentile(active, 10)), 2),
        'crest_factor_db': round(20 * math.log10((peak + 1e-9) / (float(np.sqrt(np.mean(signal * signal))) + 1e-9)), 2),
    }


def analyse(path):
    signal, rate = decode(path)
    result = {'file': os.path.abspath(path), 'duration_seconds': round(duration(path), 3)}
    result.update(loudness(path))
    result.update(descriptors(signal, rate))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+')
    parser.add_argument('--output')
    args = parser.parse_args()
    payload = [analyse(path) for path in args.files]
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as handle:
            handle.write(rendered + '\n')
    print(rendered)


if __name__ == '__main__':
    main()
