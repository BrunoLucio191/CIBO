#!/usr/bin/env python3
"""Validate a YouTube cut and optionally compare it with an online reference window."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def probe(path: Path) -> dict:
    result = run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size,format_name:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
        "-of", "json", str(path),
    ])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def ratio(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    return float(Fraction(value))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final", type=Path)
    parser.add_argument("--expected-duration", type=float)
    parser.add_argument("--duration-tolerance", type=float, default=0.20)
    parser.add_argument("--min-width", type=int)
    parser.add_argument("--min-height", type=int)
    parser.add_argument("--expected-fps", type=float)
    parser.add_argument("--fps-tolerance", type=float, default=0.05)
    parser.add_argument("--reference", type=Path, help="Fresh YouTube reference window")
    parser.add_argument("--reference-offset", type=float, default=0.0,
                        help="Seconds from reference start to final start")
    parser.add_argument("--min-ssim", type=float, default=0.97)
    parser.add_argument("--min-audio-psnr", type=float, default=20.0)
    args = parser.parse_args()

    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    try:
        if not args.final.is_file():
            raise RuntimeError(f"file not found: {args.final}")
        data = probe(args.final)
        streams = data.get("streams", [])
        videos = [s for s in streams if s.get("codec_type") == "video"]
        audios = [s for s in streams if s.get("codec_type") == "audio"]
        duration = float(data["format"]["duration"])
        size = int(data["format"].get("size", 0))

        check("nonempty_file", size > 0, f"{size} bytes")
        check("video_stream", bool(videos), videos[0].get("codec_name", "missing") if videos else "missing")
        check("audio_stream", bool(audios), audios[0].get("codec_name", "missing") if audios else "missing")

        if videos:
            video = videos[0]
            width, height = int(video.get("width", 0)), int(video.get("height", 0))
            fps = ratio(video.get("r_frame_rate"))
            if args.min_width:
                check("minimum_width", width >= args.min_width, f"{width} >= {args.min_width}")
            if args.min_height:
                check("minimum_height", height >= args.min_height, f"{height} >= {args.min_height}")
            if args.expected_fps is not None:
                check("frame_rate", abs(fps - args.expected_fps) <= args.fps_tolerance,
                      f"{fps:.3f} vs {args.expected_fps:.3f}")

        if args.expected_duration is not None:
            delta = abs(duration - args.expected_duration)
            check("duration", delta <= args.duration_tolerance,
                  f"{duration:.3f}s; expected {args.expected_duration:.3f}s; delta {delta:.3f}s")

        decoded = run([
            "ffmpeg", "-v", "error", "-i", str(args.final),
            "-map", "0:v:0", "-map", "0:a:0", "-f", "null", "-",
        ])
        check("full_decode", decoded.returncode == 0,
              "ok" if decoded.returncode == 0 else decoded.stderr.strip()[-1000:])

        if args.reference:
            if not args.reference.is_file():
                check("reference_exists", False, str(args.reference))
            else:
                end = args.reference_offset + duration
                graph = (
                    "[0:v]setpts=PTS-STARTPTS[v0];"
                    f"[1:v]trim=start={args.reference_offset}:end={end},setpts=PTS-STARTPTS[v1];"
                    "[v0][v1]ssim[vout];"
                    "[0:a]asetpts=PTS-STARTPTS[a0];"
                    f"[1:a]atrim=start={args.reference_offset}:end={end},asetpts=PTS-STARTPTS[a1];"
                    "[a0][a1]apsnr[aout]"
                )
                compared = run([
                    "ffmpeg", "-hide_banner", "-i", str(args.final), "-i", str(args.reference),
                    "-filter_complex", graph, "-map", "[vout]", "-map", "[aout]",
                    "-f", "null", "-",
                ])
                ssim_match = re.search(r"All:([0-9.]+)", compared.stderr)
                psnr_values = [float(v) for v in re.findall(r"PSNR ch\d+: ([0-9.]+)", compared.stderr)]
                ssim = float(ssim_match.group(1)) if ssim_match else 0.0
                audio_psnr = min(psnr_values) if psnr_values else 0.0
                check("source_video_match", compared.returncode == 0 and ssim >= args.min_ssim,
                      f"SSIM {ssim:.6f}; minimum {args.min_ssim:.6f}")
                check("source_audio_match", compared.returncode == 0 and audio_psnr >= args.min_audio_psnr,
                      f"PSNR {audio_psnr:.3f} dB; minimum {args.min_audio_psnr:.3f} dB")

    except Exception as exc:
        check("validator", False, str(exc))

    passed = all(item["passed"] for item in checks)
    print(json.dumps({"status": "PASS" if passed else "FAIL", "checks": checks},
                     ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
