#!/usr/bin/env python3
"""Benchmark CPU versus available H.264 hardware encoders on a real sample."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


HW_ENCODERS = (
    "h264_videotoolbox",
    "h264_nvenc",
    "h264_qsv",
    "h264_vaapi",
    "h264_amf",
)


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def ffprobe(path: Path) -> dict:
    data = json.loads(
        run([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,profile,pix_fmt,width,height,r_frame_rate,bit_rate",
            "-of", "json", str(path),
        ]).stdout
    )
    return data


def available_encoders() -> set[str]:
    text = run(["ffmpeg", "-hide_banner", "-encoders"]).stdout
    return {name for name in ("libx264", *HW_ENCODERS) if re.search(rf"\b{re.escape(name)}\b", text)}


def device_info() -> dict:
    info = {
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "ffmpeg": run(["ffmpeg", "-version"]).stdout.splitlines()[0],
    }
    if platform.system() == "Darwin" and shutil.which("system_profiler"):
        text = run(["system_profiler", "SPDisplaysDataType"], check=False).stdout
        chips = re.findall(r"Chipset Model:\s*(.+)", text)
        cores = re.findall(r"Total Number of Cores:\s*(.+)", text)
        info["gpu"] = chips
        info["gpu_cores"] = cores
    return info


def encoder_args(name: str, target: str, maxrate: str, bufsize: str, preset: str, crf: int) -> list[str]:
    common = ["-pix_fmt", "yuv420p", "-profile:v", "high", "-maxrate", maxrate, "-bufsize", bufsize]
    if name == "libx264":
        return ["-c:v", name, "-preset", preset, "-crf", str(crf), *common]
    if name == "h264_videotoolbox":
        return ["-c:v", name, "-b:v", target, "-realtime", "false", *common]
    if name == "h264_nvenc":
        return ["-c:v", name, "-preset", "p5", "-rc", "vbr", "-cq", str(crf), "-b:v", target, *common]
    if name == "h264_qsv":
        return ["-c:v", name, "-preset", "medium", "-global_quality", str(crf), "-b:v", target, *common]
    if name == "h264_amf":
        return ["-c:v", name, "-quality", "balanced", "-b:v", target, *common]
    # VAAPI may require an explicit hardware device on some systems. Failure is reported, not hidden.
    return ["-c:v", name, "-b:v", target, *common]


def parse_ssim(stderr: str) -> float | None:
    matches = re.findall(r"All:([0-9.]+)", stderr)
    return float(matches[-1]) if matches else None


def benchmark_one(inp: Path, out: Path, name: str, start: float, seconds: float, target: str,
                  maxrate: str, bufsize: str, preset: str, crf: int) -> dict:
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(start), "-t", str(seconds),
        "-i", str(inp), "-an", *encoder_args(name, target, maxrate, bufsize, preset, crf),
        "-movflags", "+faststart", "-color_range", "tv", "-colorspace", "bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709", str(out),
    ]
    started = time.perf_counter()
    proc = run(cmd, check=False)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        return {"encoder": name, "ok": False, "error": proc.stderr[-1500:]}

    probe = ffprobe(out)
    duration = float(probe["format"].get("duration") or seconds)
    size = int(probe["format"].get("size") or out.stat().st_size)
    bitrate = int(probe["format"].get("bit_rate") or round(size * 8 / max(duration, 0.001)))
    ssim_proc = run([
        "ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(seconds), "-i", str(inp),
        "-i", str(out), "-lavfi", "[0:v][1:v]ssim", "-f", "null", "-",
    ], check=False)
    return {
        "encoder": name,
        "ok": True,
        "elapsed_seconds": round(elapsed, 3),
        "realtime_factor": round(duration / max(elapsed, 0.001), 3),
        "size_bytes": size,
        "bitrate_bps": bitrate,
        "ssim": parse_ssim(ssim_proc.stderr),
        "output": str(out),
    }


def recommend(results: list[dict], maxrate_mbps: float, priority: str) -> dict:
    cpu = next((x for x in results if x.get("ok") and x["encoder"] == "libx264"), None)
    if not cpu:
        return {"encoder": None, "reason": "benchmark CPU failed"}
    accepted = []
    for item in results:
        if not item.get("ok") or item["encoder"] == "libx264":
            continue
        speedup = cpu["elapsed_seconds"] / max(item["elapsed_seconds"], 0.001)
        ssim = item.get("ssim") or 0
        cpu_ssim = cpu.get("ssim") or 1
        speed_gate = {"speed": 1.25, "balanced": 1.5, "size": 2.0}[priority]
        inflation_gate = {"speed": float("inf"), "balanced": 1.75, "size": 1.25}[priority]
        bitrate_ok = item["bitrate_bps"] <= maxrate_mbps * 1_000_000 * 1.15
        bitrate_ok = bitrate_ok and item["bitrate_bps"] <= cpu["bitrate_bps"] * inflation_gate
        quality_ok = ssim >= 0.96 and ssim >= cpu_ssim - 0.01
        if speedup >= speed_gate and bitrate_ok and quality_ok:
            accepted.append((speedup, item))
    if accepted:
        speedup, item = max(accepted, key=lambda x: x[0])
        return {"encoder": item["encoder"], "priority": priority, "speedup_vs_cpu": round(speedup, 2), "reason": "hardware passed speed, quality and bitrate gates"}
    return {"encoder": "libx264", "priority": priority, "reason": "no hardware encoder passed every speed, quality and bitrate gate"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--start", type=float, default=1.0)
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--target-mbps", type=float, default=8.0)
    ap.add_argument("--maxrate-mbps", type=float, default=10.0)
    ap.add_argument("--priority", choices=("speed", "balanced", "size"), default="speed")
    ap.add_argument("--cpu-preset", default="medium")
    ap.add_argument("--cpu-crf", type=int, default=21)
    args = ap.parse_args()
    if not args.input.is_file():
        ap.error(f"input not found: {args.input}")

    encoders = available_encoders()
    selected = [name for name in ("libx264", *HW_ENCODERS) if name in encoders]
    target = f"{args.target_mbps:g}M"
    maxrate = f"{args.maxrate_mbps:g}M"
    bufsize = f"{args.maxrate_mbps * 2:g}M"
    with tempfile.TemporaryDirectory(prefix="encoder-benchmark-") as tmp:
        results = [
            benchmark_one(args.input, Path(tmp) / f"{name}.mp4", name, args.start, args.seconds,
                          target, maxrate, bufsize, args.cpu_preset, args.cpu_crf)
            for name in selected
        ]
        report = {
            "device": device_info(),
            "input": str(args.input),
            "input_probe": ffprobe(args.input),
            "settings": {
                "seconds": args.seconds,
                "start": args.start,
                "target_mbps": args.target_mbps,
                "maxrate_mbps": args.maxrate_mbps,
                "priority": args.priority,
                "cpu_preset": args.cpu_preset,
                "cpu_crf": args.cpu_crf,
            },
            "available_h264_encoders": selected,
            "results": results,
            "recommendation": recommend(results, args.maxrate_mbps, args.priority),
        }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
