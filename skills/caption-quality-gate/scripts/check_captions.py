#!/usr/bin/env python3
"""Deterministic caption checks plus a hardware-aware visual review sheet."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def load_caps(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("caps"), list):
        return data["caps"]
    raise ValueError("captions JSON must be a list or contain a 'caps' list")


def detect_acceleration() -> dict:
    accelerators = run(["ffmpeg", "-hide_banner", "-hwaccels"], check=False).stdout
    system = platform.system()
    hw = None
    if system == "Darwin" and "videotoolbox" in accelerators:
        hw = "videotoolbox"
    elif "cuda" in accelerators:
        hw = "cuda"
    elif "qsv" in accelerators:
        hw = "qsv"
    elif "vaapi" in accelerators:
        hw = "vaapi"
    asr = []
    for name in ("mlx_whisper", "faster_whisper", "whisper"):
        if importlib.util.find_spec(name):
            asr.append(name)
    if shutil.which("whisper-cli"):
        asr.append("whisper.cpp")
    return {"system": system, "machine": platform.machine(), "ffmpeg_hwaccel": hw, "asr_engines": asr}


def check_caps(caps: list[dict], max_chars: int, max_cps: float) -> tuple[list[dict], list[dict]]:
    errors, warnings = [], []
    previous_end = -1.0
    for i, cap in enumerate(caps):
        text = str(cap.get("t", "")).strip()
        start = float(cap.get("s", -1))
        end = float(cap.get("e", -1))
        duration = end - start
        label = {"index": i, "start": start, "end": end, "text": text}
        if not text:
            errors.append({**label, "code": "empty_text"})
        if start < 0 or end <= start:
            errors.append({**label, "code": "invalid_time"})
            continue
        if start < previous_end - 0.03:
            errors.append({**label, "code": "overlap", "previous_end": previous_end})
        previous_end = max(previous_end, end)
        if duration < 0.18:
            warnings.append({**label, "code": "too_short", "duration": round(duration, 3)})
        if duration > 6:
            warnings.append({**label, "code": "too_long", "duration": round(duration, 3)})
        cps = len(re.sub(r"\s+", "", text)) / max(duration, 0.001)
        hook_exception = i == 0 and duration >= 0.28 and len(re.sub(r"\s+", "", text)) <= 16
        if cps > max_cps and hook_exception:
            warnings.append({**label, "code": "fast_opening_hook_review", "cps": round(cps, 2)})
        elif cps > max_cps:
            errors.append({**label, "code": "cps_excessive", "cps": round(cps, 2)})
        elif cps > 24:
            warnings.append({**label, "code": "cps_high", "cps": round(cps, 2)})
        if len(text) > max_chars:
            warnings.append({**label, "code": "block_long", "characters": len(text)})
        words, emph = cap.get("w"), cap.get("em")
        if isinstance(words, list) and " ".join(words).strip() != text:
            warnings.append({**label, "code": "word_list_mismatch"})
        if isinstance(words, list) and isinstance(emph, list) and len(words) != len(emph):
            errors.append({**label, "code": "emphasis_length_mismatch"})
        if re.search(r"\b(\w+)\s+\1\b", text, flags=re.I):
            warnings.append({**label, "code": "repeated_word"})
    return errors, warnings


def sample_indices(caps: list[dict], limit: int) -> list[int]:
    if len(caps) <= limit:
        return list(range(len(caps)))
    chosen = {0, len(caps) - 1}
    chosen.add(max(range(len(caps)), key=lambda i: len(str(caps[i].get("t", "")))))
    chosen.add(max(range(len(caps)), key=lambda i: len(str(caps[i].get("t", ""))) / max(float(caps[i]["e"]) - float(caps[i]["s"]), .001)))
    for n in range(limit):
        chosen.add(round(n * (len(caps) - 1) / max(limit - 1, 1)))
    return sorted(chosen)[:limit]


def make_sheet(video: Path, caps: list[dict], out: Path, offset: float, hw: str | None, limit: int) -> dict:
    from PIL import Image, ImageDraw, ImageFont

    chosen = sample_indices(caps, limit)
    with tempfile.TemporaryDirectory(prefix="caption-sheet-") as tmp:
        td = Path(tmp)
        frames = []
        used_hw = hw
        for order, idx in enumerate(chosen):
            cap = caps[idx]
            at = offset + (float(cap["s"]) + float(cap["e"])) / 2
            frame = td / f"{order:04d}.jpg"
            prefix = ["ffmpeg", "-hide_banner", "-loglevel", "error"]
            if used_hw:
                prefix += ["-hwaccel", used_hw]
            command = prefix + ["-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", "-q:v", "3", "-y", str(frame)]
            proc = run(command, check=False)
            if proc.returncode != 0 and used_hw:
                used_hw = None
                command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=270:480", "-q:v", "3", "-y", str(frame)]
                proc = run(command, check=False)
            if proc.returncode == 0 and frame.exists():
                frames.append((idx, at, frame))
        cols, cell_w, cell_h = 4, 300, 555
        rows = math.ceil(len(frames) / cols)
        canvas = Image.new("RGB", (cols * cell_w, rows * cell_h), (16, 18, 24))
        draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
        for n, (idx, at, frame) in enumerate(frames):
            x, y = (n % cols) * cell_w, (n // cols) * cell_h
            canvas.paste(Image.open(frame).convert("RGB"), (x + 15, y + 10))
            draw.multiline_text((x + 15, y + 495), f"#{idx}  {at:.2f}s\n{caps[idx].get('t','')}", font=font, fill="white", spacing=3)
        out.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out, quality=92)
    return {"path": str(out), "sampled_caption_indices": chosen, "hardware_decode": used_hw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--captions", required=True, type=Path)
    ap.add_argument("--video", type=Path)
    ap.add_argument("--sheet", type=Path)
    ap.add_argument("--output-json", type=Path)
    ap.add_argument("--caption-offset", type=float, default=0.0)
    ap.add_argument("--max-block-chars", type=int, default=24)
    ap.add_argument("--max-cps", type=float, default=32.0)
    ap.add_argument("--sheet-limit", type=int, default=24)
    args = ap.parse_args()
    caps = load_caps(args.captions)
    hardware = detect_acceleration()
    errors, warnings = check_caps(caps, args.max_block_chars, args.max_cps)
    sheet = None
    if args.video and args.sheet:
        sheet = make_sheet(args.video, caps, args.sheet, args.caption_offset, hardware["ffmpeg_hwaccel"], args.sheet_limit)
    report = {
        "captions": str(args.captions), "video": str(args.video) if args.video else None,
        "caption_count": len(caps), "hardware": hardware, "errors": errors, "warnings": warnings,
        "visual_sheet": sheet,
        "automated_status": "FAIL" if errors else ("REVIEW_REQUIRED" if warnings else "AUTOMATED_PASS"),
        "final_status": "REVIEW_REQUIRED",
        "note": "Final PASS requires contextual audio comparison and visual sheet inspection.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
