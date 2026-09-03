#!/usr/bin/env python3
"""Run caption and final-video gates for every clip in one or more Content Hub jobs."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from pathlib import Path


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def run_one(item: tuple[Path, str], args: argparse.Namespace) -> dict:
    job_path, key = item
    job = json.loads(job_path.read_text(encoding="utf-8"))
    plan = json.loads((Path(job["work"]) / "plan.json").read_text(encoding="utf-8"))
    clip = plan[key]
    base = clip.get("filename", key)
    video = Path(job["outdir"]) / f"{base}.mp4"
    cover = Path(job["outdir"]) / f"CAPA - {base}.png"
    tag = f"{slug(job_path.parent.name)}_{key}"
    cap_report = args.qa_dir / "captions" / f"{tag}.json"
    cap_sheet = args.qa_dir / "captions" / f"{tag}.jpg"
    final_report = args.qa_dir / "final" / f"{tag}.json"
    final_sheet = args.qa_dir / "final" / f"{tag}.jpg"
    captions = Path(job["work"]) / f"captions_{key}.json"
    cap_cmd = [sys.executable, "-B", str(args.caption_script), "--captions", str(captions),
               "--video", str(video), "--caption-offset", str(1 / 30),
               "--sheet", str(cap_sheet), "--output-json", str(cap_report)]
    cap_proc = subprocess.run(cap_cmd, text=True, capture_output=True)
    final_cmd = [sys.executable, "-B", str(args.safety_script), "--video", str(video),
                 "--plan", str(Path(job["work"]) / "plan.json"), "--clip", key,
                 "--cover", str(cover), "--sheet", str(final_sheet), "--output-json", str(final_report)]
    final_proc = subprocess.run(final_cmd, text=True, capture_output=True)
    cap_data = json.loads(cap_report.read_text(encoding="utf-8")) if cap_report.exists() else None
    final_data = json.loads(final_report.read_text(encoding="utf-8")) if final_report.exists() else None
    return {
        "job": str(job_path), "clip": key, "video": str(video),
        "caption_status": cap_data.get("automated_status") if cap_data else "TOOL_ERROR",
        "caption_errors": len(cap_data.get("errors", [])) if cap_data else None,
        "caption_warnings": len(cap_data.get("warnings", [])) if cap_data else None,
        "final_status": final_data.get("automated_status") if final_data else "TOOL_ERROR",
        "final_errors": len(final_data.get("errors", [])) if final_data else None,
        "final_warnings": len(final_data.get("warnings", [])) if final_data else None,
        "caption_tool_exit": cap_proc.returncode, "final_tool_exit": final_proc.returncode,
        "caption_report": str(cap_report), "final_report": str(final_report),
        "caption_sheet": str(cap_sheet), "final_sheet": str(final_sheet),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", nargs="+", required=True, type=Path)
    ap.add_argument("--qa-dir", required=True, type=Path)
    ap.add_argument("--caption-script", required=True, type=Path)
    ap.add_argument("--safety-script", required=True, type=Path)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    args.qa_dir.mkdir(parents=True, exist_ok=True)
    items = []
    for path in args.jobs:
        job = json.loads(path.read_text(encoding="utf-8"))
        items.extend((path, key) for key in job["clips"])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(lambda item: run_one(item, args), items))
    summary = {
        "clips": results,
        "automated_failures": sum(1 for x in results if x["caption_status"] == "FAIL" or x["final_status"] == "FAIL"),
        "note": "Final PASS still requires visual sheet inspection and final audio/context review.",
    }
    out = args.qa_dir / "summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(1 if summary["automated_failures"] else 0)


if __name__ == "__main__":
    main()
