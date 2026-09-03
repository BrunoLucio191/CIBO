#!/usr/bin/env python3
"""Automated final-video gate. Visual/audio review is still required for final PASS."""

from __future__ import annotations

import argparse
import json
import math
import platform
import re
import subprocess
import tempfile
from pathlib import Path


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def probe(path: Path) -> dict:
    proc = run(["ffprobe", "-v", "error", "-show_entries",
                "format=duration,size,bit_rate,format_name:stream=index,codec_type,codec_name,profile,pix_fmt,width,height,r_frame_rate,avg_frame_rate,bit_rate,color_range,color_space,color_transfer,color_primaries,sample_rate,channels",
                "-of", "json", str(path)])
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def hwaccel() -> str | None:
    text = run(["ffmpeg", "-hide_banner", "-hwaccels"]).stdout
    if platform.system() == "Darwin" and "videotoolbox" in text:
        return "videotoolbox"
    for name in ("cuda", "qsv", "vaapi"):
        if name in text:
            return name
    return None


def parse_loudness(stderr: str) -> dict:
    integrated = re.findall(r"\bI:\s*(-?[0-9.]+) LUFS", stderr)
    peaks = re.findall(r"Peak:\s*(-?[0-9.]+) dBFS", stderr)
    return {
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "true_peak_dbfs": float(peaks[-1]) if peaks else None,
    }


def parse_intervals(stderr: str, key: str) -> list[dict]:
    starts = [float(x) for x in re.findall(rf"{key}_start:([0-9.]+)", stderr)]
    durations = [float(x) for x in re.findall(rf"{key}_duration:([0-9.]+)", stderr)]
    return [{"start": s, "duration": durations[i] if i < len(durations) else None} for i, s in enumerate(starts)]


def expected_from_plan(path: Path | None, clip: str | None) -> dict | None:
    if not path or not clip:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    item = data.get(clip)
    if not item:
        return None
    return {
        "clip": clip, "content_duration": item.get("total"),
        "headline": item.get("headline"), "broll_count": len(item.get("broll", [])),
        "lettering_count": len(item.get("letterings", [])),
        "broll_events": [{"t": x.get("t"), "duration": x.get("duration")} for x in item.get("broll", [])],
        "lettering_events": [{"t": x.get("t"), "duration": x.get("duration"), "text": x.get("text")} for x in item.get("letterings", [])],
    }


def compare_cover(video: Path, cover: Path) -> dict:
    from PIL import Image
    import numpy as np

    if not cover.is_file():
        return {"ok": False, "error": "cover file missing", "path": str(cover)}
    with tempfile.TemporaryDirectory(prefix="cover-check-") as tmp:
        frame = Path(tmp) / "frame0.png"
        proc = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                    "-vf", "select=eq(n\\,0)", "-frames:v", "1", "-y", str(frame)])
        if proc.returncode or not frame.exists():
            return {"ok": False, "error": "could not extract frame zero", "detail": proc.stderr[-800:]}
        a = np.asarray(Image.open(frame).convert("RGB").resize((270, 480))).astype(np.float32)
        b = np.asarray(Image.open(cover).convert("RGB").resize((270, 480))).astype(np.float32)
        mad = float(np.abs(a - b).mean())
        return {"ok": mad <= 8.0, "mean_absolute_difference": round(mad, 4), "path": str(cover)}


def make_sheet(video: Path, out: Path, duration: float, hardware: str | None, frames: int = 16) -> dict:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    times = [0.05] + [duration * (i + 1) / (frames + 1) for i in range(frames - 2)] + [max(0.05, duration - 0.2)]
    metrics, images = [], []
    with tempfile.TemporaryDirectory(prefix="video-qa-") as tmp:
        td = Path(tmp)
        used_hw = hardware
        for i, at in enumerate(times):
            dest = td / f"{i:03d}.jpg"
            prefix = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
            if used_hw:
                prefix += ["-hwaccel", used_hw]
            cmd = prefix + ["-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", "-q:v", "2", "-y", str(dest)]
            proc = run(cmd)
            if proc.returncode and used_hw:
                used_hw = None
                cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", "-q:v", "2", "-y", str(dest)]
                proc = run(cmd)
            if proc.returncode or not dest.exists():
                continue
            image = Image.open(dest).convert("RGB")
            arr = np.asarray(image).astype(np.float32)
            luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
            gx = np.abs(np.diff(luma, axis=1)).mean()
            gy = np.abs(np.diff(luma, axis=0)).mean()
            block_boundary = np.abs(luma[:, 7::8] - luma[:, 8::8]).mean() if luma.shape[1] > 16 else 0
            metrics.append({
                "time": round(at, 3), "luma_mean": round(float(luma.mean()), 2),
                "luma_p05": round(float(np.percentile(luma, 5)), 2), "luma_p95": round(float(np.percentile(luma, 95)), 2),
                "detail_gradient": round(float((gx + gy) / 2), 3), "block_boundary": round(float(block_boundary), 3),
            })
            images.append((at, image))
        cols, cell_w, cell_h = 4, 300, 535
        rows = math.ceil(len(images) / cols)
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (14, 16, 22))
        draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
        for n, (at, image) in enumerate(images):
            x, y = (n % cols) * cell_w, (n // cols) * cell_h
            sheet.paste(image, (x + 15, y + 10))
            draw.text((x + 15, y + 495), f"{at:.2f}s", font=font, fill="white")
        out.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out, quality=92)
    return {"path": str(out), "hardware_decode": used_hw, "frame_metrics": metrics}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--plan", type=Path)
    ap.add_argument("--clip")
    ap.add_argument("--cover", type=Path)
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--min-video-mbps", type=float, default=1.5)
    ap.add_argument("--max-video-mbps", type=float, default=10.0)
    args = ap.parse_args()
    info = probe(args.video)
    videos = [x for x in info.get("streams", []) if x.get("codec_type") == "video"]
    audios = [x for x in info.get("streams", []) if x.get("codec_type") == "audio"]
    errors, warnings = [], []
    if not videos: errors.append({"code": "missing_video"})
    if not audios: errors.append({"code": "missing_audio"})
    v = videos[0] if videos else {}
    duration = float(info.get("format", {}).get("duration") or 0)
    video_bitrate = int(v.get("bit_rate") or 0)
    if (v.get("width"), v.get("height")) != (args.width, args.height):
        errors.append({"code": "wrong_dimensions", "actual": [v.get("width"), v.get("height")]})
    rate = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
    num, den = [float(x) for x in rate.split("/")]
    actual_fps = num / den if den else 0
    if abs(actual_fps - args.fps) > 0.05: errors.append({"code": "wrong_fps", "actual": actual_fps})
    if v.get("codec_name") != "h264": errors.append({"code": "wrong_video_codec", "actual": v.get("codec_name")})
    if v.get("pix_fmt") != "yuv420p": errors.append({"code": "wrong_pixel_format", "actual": v.get("pix_fmt")})
    if video_bitrate and video_bitrate < args.min_video_mbps * 1_000_000: warnings.append({"code": "video_bitrate_low", "actual": video_bitrate})
    if video_bitrate and video_bitrate > args.max_video_mbps * 1_000_000: errors.append({"code": "video_bitrate_high", "actual": video_bitrate})
    color = {k: v.get(k) for k in ("color_range", "color_space", "color_transfer", "color_primaries")}
    if color != {"color_range": "tv", "color_space": "bt709", "color_transfer": "bt709", "color_primaries": "bt709"}:
        errors.append({"code": "incomplete_rec709_metadata", "actual": color})
    decode = run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(args.video), "-f", "null", "-"])
    if decode.returncode: errors.append({"code": "full_decode_failed", "detail": decode.stderr[-1500:]})
    audio = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(args.video), "-af", "ebur128=peak=true", "-f", "null", "-"])
    loudness = parse_loudness(audio.stderr)
    if loudness["integrated_lufs"] is not None and not (-19 <= loudness["integrated_lufs"] <= -13):
        warnings.append({"code": "loudness_outside_social_range", "actual": loudness["integrated_lufs"]})
    if loudness["true_peak_dbfs"] is not None and loudness["true_peak_dbfs"] > -1:
        errors.append({"code": "true_peak_too_high", "actual": loudness["true_peak_dbfs"]})
    detect = run(["ffmpeg", "-hide_banner", "-i", str(args.video), "-vf", "blackdetect=d=0.5:pix_th=0.05,freezedetect=n=0.003:d=2", "-an", "-f", "null", "-"])
    black = parse_intervals(detect.stderr, "black")
    freeze = parse_intervals(detect.stderr, "freeze")
    unexpected_black = [x for x in black if x["start"] > 1.2 and x["start"] < max(1.2, duration - 1.5)]
    if unexpected_black: warnings.append({"code": "unexpected_black_frames", "events": unexpected_black})
    if freeze: warnings.append({"code": "long_freeze", "events": freeze})
    expected = expected_from_plan(args.plan, args.clip)
    if expected and expected.get("content_duration"):
        expected_total = float(expected["content_duration"]) + 0.8
        if abs(duration - expected_total) > 2.0:
            errors.append({"code": "duration_mismatch", "actual": duration, "expected_approx": expected_total})
    cover_check = compare_cover(args.video, args.cover) if args.cover else None
    if cover_check and not cover_check.get("ok"):
        errors.append({"code": "cover_frame_zero_mismatch", "detail": cover_check})
    sheet = make_sheet(args.video, args.sheet, duration, hwaccel()) if args.sheet else None
    if sheet:
        metrics = sheet["frame_metrics"]
        dark = [x for x in metrics[1:-1] if x["luma_mean"] < 32]
        bright = [x for x in metrics[1:-1] if x["luma_mean"] > 225]
        low_detail = [x for x in metrics[1:-1] if x["detail_gradient"] < 2.0]
        blocky = [x for x in metrics[1:-1] if x["detail_gradient"] and x["block_boundary"] / x["detail_gradient"] > 2.2]
        if len(dark) > len(metrics) * .35: warnings.append({"code": "persistent_underexposure", "frames": dark})
        if len(bright) > len(metrics) * .35: warnings.append({"code": "persistent_overexposure", "frames": bright})
        if len(low_detail) > len(metrics) * .35: warnings.append({"code": "persistent_low_detail_or_blur", "frames": low_detail})
        if len(blocky) > len(metrics) * .35: warnings.append({"code": "possible_macroblocking", "frames": blocky})
    report = {
        "video": str(args.video), "probe": info, "expected": expected, "hardware_decode": hwaccel(),
        "full_decode_ok": decode.returncode == 0, "loudness": loudness, "black_events": black, "freeze_events": freeze,
        "cover_check": cover_check,
        "errors": errors, "warnings": warnings, "visual_sheet": sheet,
        "automated_status": "FAIL" if errors else ("REVIEW_REQUIRED" if warnings else "AUTOMATED_PASS"),
        "final_status": "REVIEW_REQUIRED",
        "note": "Final PASS requires visual sheet inspection, final audio listening and job comparison.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
