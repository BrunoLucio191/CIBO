#!/usr/bin/env python3
"""Print an SRT as timestamped text blocks for editorial selection."""
import argparse
import html
import re


TIME = re.compile(r"(\d\d):(\d\d):(\d\d)[,.](\d{3})")


def seconds(value):
    h, m, s, ms = map(int, TIME.search(value).groups())
    return h * 3600 + m * 60 + s + ms / 1000


def stamp(value):
    m, s = divmod(int(value), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def cues(path):
    raw = open(path, encoding="utf-8-sig").read().strip()
    for block in re.split(r"\n\s*\n", raw):
        lines = block.splitlines()
        time_line = next((line for line in lines if "-->" in line), None)
        if not time_line:
            continue
        start, end = [seconds(part) for part in time_line.split("-->")]
        idx = lines.index(time_line)
        text = " ".join(lines[idx + 1 :])
        text = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        if text:
            yield start, end, text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("srt")
    parser.add_argument("--seconds", type=float, default=15)
    args = parser.parse_args()
    bucket = []
    block_start = block_end = None
    for start, end, text in cues(args.srt):
        if block_start is None:
            block_start = start
        if bucket and end - block_start > args.seconds:
            print(f"[{stamp(block_start)} - {stamp(block_end)}] {' '.join(bucket)}")
            bucket, block_start = [], start
        bucket.append(text)
        block_end = end
    if bucket:
        print(f"[{stamp(block_start)} - {stamp(block_end)}] {' '.join(bucket)}")


if __name__ == "__main__":
    main()
