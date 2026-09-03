#!/usr/bin/env python3
"""Sample and smooth the horizontal face centre for 2:3 and 9:16 crops."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def even(value):
    return int(round(value / 2.0) * 2)


def crop_data(times, centers, duration, source_width, crop_width):
    key_times = list(np.arange(0, duration, 1.0)) + [duration]
    crop_x = np.interp(key_times, times, centers) - crop_width / 2.0
    crop_x = np.clip(np.round(crop_x / 2) * 2, 0, source_width - crop_width)

    expression = f"{crop_x[-1]:.0f}"
    for index in range(len(key_times) - 2, -1, -1):
        t0, t1 = key_times[index], key_times[index + 1]
        x0, x1 = crop_x[index], crop_x[index + 1]
        linear = f"{x0:.0f}+({x1 - x0:.0f})*(t-{t0:.3f})/{t1 - t0:.3f}"
        expression = f"if(lt(t,{t1:.3f}),{linear},{expression})"

    return {
        "crop_width": crop_width,
        "x_expression": expression,
        "timeline": [
            {"t": round(float(t), 3), "crop_x": int(x)}
            for t, x in zip(key_times, crop_x)
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--output", required=True)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()

    capture = cv2.VideoCapture(args.video)
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or width <= 0 or height <= 0:
        raise SystemExit("Could not read video geometry")
    duration = frame_count / fps

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    samples = []
    last_center = width / 2.0
    t = 0.0
    while t < duration:
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = capture.read()
        if not ok:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(
            gray, scaleFactor=1.08, minNeighbors=5,
            minSize=(max(60, height // 12), max(60, height // 12))
        )
        if len(faces):
            choices = []
            for x, y, w, h in faces:
                center = x + w / 2.0
                score = w * h - abs(center - last_center) * height * 0.23
                choices.append((score, center, [int(x), int(y), int(w), int(h)]))
            _, last_center, box = max(choices)
            samples.append({"t": round(t, 3), "center_x": last_center, "box": box})
        t += args.interval
    capture.release()

    if len(samples) < 3:
        samples = [
            {"t": 0.0, "center_x": width / 2.0, "box": None},
            {"t": duration, "center_x": width / 2.0, "box": None},
        ]

    times = np.array([item["t"] for item in samples], dtype=float)
    centres = np.array([item["center_x"] for item in samples], dtype=float)
    radius = max(2, round(1.0 / args.interval))
    median = np.array([
        np.median(centres[max(0, i - radius):min(len(centres), i + radius + 1)])
        for i in range(len(centres))
    ])
    if len(median) >= 3:
        median = np.convolve(
            np.pad(median, (2, 2), mode="edge"), np.ones(5) / 5, mode="valid"
        )

    foreground_width = min(width, even(height * 2 / 3))
    background_width = min(width, even(height * 9 / 16))
    result = {
        "video": str(Path(args.video).resolve()),
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "detections": len(samples),
        "foreground": crop_data(times, median, duration, width, foreground_width),
        "background": crop_data(times, median, duration, width, background_width),
    }
    Path(args.output).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "output": str(Path(args.output)),
        "detections": len(samples),
        "foreground_crop_width": foreground_width,
        "background_crop_width": background_width,
    }, indent=2))


if __name__ == "__main__":
    main()
