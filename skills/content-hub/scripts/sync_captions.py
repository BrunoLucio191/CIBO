#!/usr/bin/env python3
"""Copy human-reviewed caption JSON back into an existing plan without replanning trims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True, type=Path)
    ap.add_argument("clips", nargs="+")
    args = ap.parse_args()
    path = args.work / "plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    for key in args.clips:
        captions = json.loads((args.work / f"captions_{key}.json").read_text(encoding="utf-8"))
        plan[key]["caps"] = captions["caps"]
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("synced", ", ".join(args.clips), "->", path)


if __name__ == "__main__":
    main()
