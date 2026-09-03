#!/usr/bin/env python3
"""Recompose final deliverables from existing passA/caption/lettering stages."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True, type=Path)
    ap.add_argument("clips", nargs="+")
    args = ap.parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    work = Path(job["work"])
    os.environ.setdefault("WORK", str(work))
    os.environ.setdefault("FILMBURN", job.get("filmburn", str(HERE.parent / "assets" / "film_burn_clean.mp4")))
    os.environ.setdefault("VIDEO_ENCODER", job.get("encoder", "libx264"))
    os.environ.setdefault("VT_BITRATE", str(job.get("vt_bitrate", "8M")))
    os.environ.setdefault("VT_MAXRATE", str(job.get("vt_maxrate", "10M")))
    os.environ.setdefault("VT_BUFSIZE", str(job.get("vt_bufsize", "20M")))
    import render

    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    outdir = Path(job["outdir"])
    outdir.mkdir(parents=True, exist_ok=True)
    for key in args.clips:
        clip = plan[key]
        basename = clip.get("filename", key)
        out = outdir / f"{basename}.mp4"
        cover = work / f"capa_{key}.png"
        render.final(
            clip, str(work / f"A_{key}.mp4"), str(work / f"I_{key}.mp4"), str(out),
            cover=str(cover), preset=job.get("preset", "veryfast"), crf=job.get("crf", 21),
            extra=job.get("extra_v", ""),
        )
        shutil.copy2(cover, outdir / f"CAPA - {basename}.png")
        print(f"{key} DONE -> {out}", flush=True)


if __name__ == "__main__":
    main()
