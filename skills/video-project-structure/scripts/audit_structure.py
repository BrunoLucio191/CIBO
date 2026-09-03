#!/usr/bin/env python3
"""Non-destructive structure audit for video projects and Drive staging folders."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


REQUIRED = {
    "01_sources": ("masters", "audio", "proxies"),
    "02_transcripts": (),
    "03_assets": ("brand", "fonts", "music", "sfx", "vfx_overlays", "stock_local_only", "licenses"),
    "04_work": (),
    "05_qa": (),
    "06_deliverables": (),
    "07_manifests": (),
}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".mxf", ".avi", ".webm", ".mts", ".m2ts"}
RAW_HINT = re.compile(r"(^|[_ -])(master|raw|bruto|gravacao|gravação|proxy|camera|cam\d|obs)([_ .-]|$)", re.I)
STOCK_HINT = re.compile(r"(stock|pexels|pixabay|coverr|videvo|broll|b-roll)", re.I)
VFX_HINT = re.compile(r"(vfx|fsx|overlay|transition|transicao|transição|film.?burn|light.?leak|glitch|particle)", re.I)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def init(root: Path) -> None:
    for top, children in REQUIRED.items():
        (root / top).mkdir(parents=True, exist_ok=True)
        for child in children:
            (root / top / child).mkdir(parents=True, exist_ok=True)


def audit(root: Path, drive_staging: bool, hashes: bool) -> dict:
    errors, warnings = [], []
    for top, children in REQUIRED.items():
        if not (root / top).is_dir():
            errors.append({"code": "missing_directory", "path": top})
        for child in children:
            rel = f"{top}/{child}"
            if not (root / rel).is_dir():
                warnings.append({"code": "missing_subdirectory", "path": rel})
    files = [p for p in root.rglob("*") if p.is_file()]
    for path in files:
        rel = path.relative_to(root).as_posix()
        top = rel.split("/", 1)[0]
        if top not in REQUIRED:
            warnings.append({"code": "loose_root_item", "path": rel})
        if re.search(r"(?:final[_ -]?final|teste\d*|novo\d*)", path.stem, re.I):
            warnings.append({"code": "unstable_name", "path": rel})
        if drive_staging and path.suffix.lower() in VIDEO_EXT:
            if RAW_HINT.search(rel):
                errors.append({"code": "raw_video_forbidden_in_drive", "path": rel})
            elif STOCK_HINT.search(rel):
                errors.append({"code": "stock_video_forbidden_in_drive", "path": rel})
            elif not VFX_HINT.search(rel):
                errors.append({"code": "unclassified_video_forbidden_in_drive", "path": rel})
    duplicates = []
    if hashes:
        groups = defaultdict(list)
        for path in files:
            groups[(path.stat().st_size, sha256(path))].append(path.relative_to(root).as_posix())
        duplicates = [paths for paths in groups.values() if len(paths) > 1]
    return {
        "root": str(root), "drive_staging": drive_staging,
        "errors": errors, "warnings": warnings, "duplicates": duplicates,
        "status": "FAIL" if errors else ("REVIEW_REQUIRED" if warnings else "PASS"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--drive-staging", action="store_true")
    ap.add_argument("--hashes", action="store_true")
    ap.add_argument("--output-json", type=Path)
    args = ap.parse_args()
    if args.init:
        init(args.root)
    report = audit(args.root, args.drive_staging, args.hashes)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(1 if report["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
