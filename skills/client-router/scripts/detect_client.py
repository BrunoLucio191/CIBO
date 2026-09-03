#!/usr/bin/env python3
"""Match free text (folder name, SRT title, user brief) against known clients.

Usage:
    python3 detect_client.py "Bombordo e Boreste - Ep 42.srt"
    python3 detect_client.py --registry custom-registry.json "texto"

This is a heuristic alias match to support, not replace, judgment: a hit still
needs a human/agent to confirm before delegating to that client's skill, and no
hit means "ask the user" rather than falling back to a guess.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_REGISTRY = Path(__file__).resolve().parent.parent / "references" / "client-registry.json"


def load_registry(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def match(text: str, registry: dict) -> list[str]:
    haystack = text.lower()
    return [
        client
        for client, info in registry.items()
        if any(alias in haystack for alias in info.get("aliases", []))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Texto a testar: nome de pasta, marca, trecho de SRT etc.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    args = parser.parse_args()

    registry = load_registry(args.registry)
    hits = match(args.text, registry)

    if not hits:
        print("Nenhum cliente conhecido identificado. Não assuma um fallback — "
              "pergunte ao usuário de qual cliente é o material, ou confirme "
              "que é um job genérico para 'podcast-reels'.")
    elif len(hits) == 1:
        print(f"Cliente identificado: {hits[0]}  ->  skills/{hits[0]}/")
    else:
        print("Mais de um cliente bateu com o texto — desambigue antes de seguir: "
              + ", ".join(hits))


if __name__ == "__main__":
    main()
