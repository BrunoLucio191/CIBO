#!/usr/bin/env python3
"""Select the cleanest speech track and enhance it with Spotify Pedalboard."""
import argparse
import json
import math
import os
import subprocess
import tempfile

import numpy as np
from pedalboard import (
    Compressor,
    Gain,
    HighShelfFilter,
    HighpassFilter,
    Limiter,
    LowShelfFilter,
    LowpassFilter,
    PeakFilter,
    Pedalboard,
)
from pedalboard.io import AudioFile


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def audio_streams(path):
    data = json.loads(
        run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index:stream_tags=title",
                "-of", "json", path,
            ],
            capture_output=True,
            text=True,
        ).stdout
    )
    return [
        {"audio_index": pos, "stream_index": item["index"],
         "title": item.get("tags", {}).get("title", f"audio_{pos}")}
        for pos, item in enumerate(data.get("streams", []))
    ]


def media_duration(path):
    return float(run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ], capture_output=True, text=True).stdout.strip())


def sample(path, audio_index, start, duration, rate=16000):
    raw = run(
        [
            "ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration),
            "-i", path, "-map", f"0:a:{audio_index}", "-ac", "1", "-ar", str(rate),
            "-f", "f32le", "-",
        ],
        capture_output=True,
    ).stdout
    return np.frombuffer(raw, dtype=np.float32)


def metrics(signal, rate=16000):
    if signal.size < rate:
        return {"score": -999.0, "reason": "faixa curta ou vazia"}
    frame = max(1, int(rate * 0.04))
    usable = signal[: signal.size - signal.size % frame].reshape(-1, frame)
    rms = np.sqrt(np.mean(usable * usable, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    speech = float(np.percentile(db, 75))
    noise = float(np.percentile(db, 15))
    snr = speech - noise
    clipping = float(np.mean(np.abs(signal) >= 0.985))
    silence = float(np.mean(db < -55))
    dc = float(abs(np.mean(signal)))
    score = snr - clipping * 900 - max(0, -34 - speech) * 0.7 - silence * 3 - dc * 40
    return {
        "score": round(score, 3),
        "speech_db": round(speech, 2),
        "noise_db": round(noise, 2),
        "snr_db": round(snr, 2),
        "clipping_ratio": round(clipping, 6),
        "silence_ratio": round(silence, 4),
    }


def choose(path, start=None, duration=120):
    path = os.path.abspath(path)
    tracks = audio_streams(path)
    total = media_duration(path)
    if start is None:
        window = min(duration / 3, max(8, total / 8))
        starts = [max(0, total * fraction - window / 2) for fraction in (0.12, 0.5, 0.82)]
    else:
        window, starts = duration, [start]
    for track in tracks:
        chunks = [sample(path, track["audio_index"], point, window) for point in starts]
        track.update(metrics(np.concatenate([chunk for chunk in chunks if chunk.size])))
        track["sample_windows"] = [[round(point, 3), round(window, 3)] for point in starts]
    if not tracks:
        raise RuntimeError("nenhuma faixa de áudio encontrada")
    return max(tracks, key=lambda item: item["score"]), tracks


def speech_level_db(signal, rate=48000):
    """Robust speech level used to avoid crushing already-hot OBS tracks."""
    if signal.size < rate:
        return -24.0
    mono = np.mean(signal, axis=0) if signal.ndim > 1 else signal
    frame = max(1, int(rate * 0.04))
    usable = mono[: mono.size - mono.size % frame].reshape(-1, frame)
    rms = np.sqrt(np.mean(usable * usable, axis=1) + 1e-12)
    return float(np.percentile(20 * np.log10(rms + 1e-9), 75))


def enhance(path, audio_index, output, start=None, duration=None):
    path = os.path.abspath(path)
    with tempfile.TemporaryDirectory(prefix="content-hub-audio-") as tmpdir:
        source = os.path.join(tmpdir, "selected.wav")
        probe_start = 0 if start is None else start
        probe_duration = min(60, media_duration(path) - probe_start) if duration is None else duration
        probe = sample(path, audio_index, probe_start, probe_duration, rate=48000)
        probe_metrics = metrics(probe, rate=48000)
        prefilters = []
        if probe_metrics.get("clipping_ratio", 0) >= 0.0005:
            prefilters.append("adeclip")
        command = ["ffmpeg", "-v", "error", "-y"]
        if start is not None:
            command += ["-ss", str(start)]
        command += ["-i", path]
        if duration is not None:
            command += ["-t", str(duration)]
        command += ["-map", f"0:a:{audio_index}"]
        if prefilters:
            command += ["-af", ",".join(prefilters)]
        command += [
            "-ac", "1", "-ar", "48000",
            "-c:a", "pcm_f32le", source,
        ]
        run(command)
        with AudioFile(source) as src:
            signal = src.read(src.frames)
            level = speech_level_db(signal, src.samplerate)
            adaptive_gain = float(np.clip(-17.0 - level, -12.0, 7.0))
            board = Pedalboard([
                HighpassFilter(cutoff_frequency_hz=70),
                LowpassFilter(cutoff_frequency_hz=16000),
                LowShelfFilter(cutoff_frequency_hz=160, gain_db=-1.0, q=0.75),
                PeakFilter(cutoff_frequency_hz=280, gain_db=-1.0, q=0.75),
                Gain(gain_db=adaptive_gain),
                Compressor(threshold_db=-18, ratio=1.75, attack_ms=20, release_ms=170),
                PeakFilter(cutoff_frequency_hz=3200, gain_db=-0.35, q=0.8),
                HighShelfFilter(cutoff_frequency_hz=7500, gain_db=-1.25, q=0.7),
                Limiter(threshold_db=-2.0, release_ms=120),
                Gain(gain_db=-1.5),
            ])
            processed = board(signal, src.samplerate)
            with AudioFile(output, "w", src.samplerate, src.num_channels) as dst:
                dst.write(processed)
        return {
            "speech_level_db": round(level, 2),
            "adaptive_gain_db": round(adaptive_gain, 2),
            "declipped": bool(prefilters),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--track", type=int, help="índice de áudio 0-based; omita para escolher automaticamente")
    parser.add_argument("--sample-start", type=float)
    parser.add_argument("--sample-duration", type=float, default=120)
    parser.add_argument("--start", type=float, help="início do trecho a tratar, em segundos")
    parser.add_argument("--duration", type=float, help="duração do trecho a tratar, em segundos")
    parser.add_argument("--report")
    args = parser.parse_args()
    selected, report = choose(args.input, args.sample_start, args.sample_duration)
    if args.track is not None:
        selected = next(item for item in report if item["audio_index"] == args.track)
    enhance(args.input, selected["audio_index"], args.output, args.start, args.duration)
    payload = {"input": args.input, "selected": selected, "tracks": report, "output": args.output}
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
