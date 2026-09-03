#!/usr/bin/env python3
"""Transcribe final-cut WAV files with MLX/Metal and cache auditable JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def serializable(value):
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    ap.add_argument("--language", default="pt")
    ap.add_argument(
        "--initial-prompt",
        default=(
            "Entrevista empresarial em português brasileiro. Content Hub, SEBRAE, "
            "empreendedorismo, inovação, sustentabilidade, Fator R, INSS, "
            "propriedade intelectual, patente, software, marca, cultivar."
        ),
    )
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    import mlx_whisper

    for audio in args.inputs:
        digest = sha256(audio)
        parent = audio.parent.parent.name.replace(" ", "_")
        out = args.output_dir / f"{parent}__{audio.stem}.json"
        if out.exists():
            cached = json.loads(out.read_text(encoding="utf-8"))
            if cached.get("audio_sha256") == digest and cached.get("model") == args.model:
                print(f"CACHED {audio}", flush=True)
                continue
        result = mlx_whisper.transcribe(
            str(audio), path_or_hf_repo=args.model, language=args.language,
            task="transcribe", word_timestamps=True, verbose=False,
            initial_prompt=args.initial_prompt,
            condition_on_previous_text=True,
        )
        payload = {
            "audio": str(audio.resolve()),
            "audio_sha256": digest,
            "model": args.model,
            "language_requested": args.language,
            "result": serializable(result),
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"DONE {audio} -> {out}", flush=True)


if __name__ == "__main__":
    main()
