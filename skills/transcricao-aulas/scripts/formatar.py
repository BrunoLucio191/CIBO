#!/usr/bin/env python3
"""Converte o JSON do transcrever_lote.py (ou do mlx_whisper) em TXT com tempo e SRT.

Uso: python3 formatar.py ARQ.json [ARQ2.json ...] --saida PASTA [--titulo "Módulo 1 — Aula 2"]
      [--correcoes correcoes.json] [--bloco 20] [--offset 0]

- TXT: blocos de ~20 s no formato "[hh:mm:ss - hh:mm:ss] texto", no tempo da gravação.
  O usuário usa a transcrição para achar o momento na timeline: sem tempo ela é "inútil".
- Pausas longas (intervalo, almoço) aparecem como "[PAUSA / SEM FALA hh:mm:ss - hh:mm:ss (N min)]".
- SRT limpo, sem tags.
- correcoes.json: {"errado": "certo"} aplicado com limite de palavra (termos técnicos, nomes).
- --offset S soma S segundos a todos os tempos (ex.: gravação que começa no meio de outra).
"""
import argparse, json, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("jsons", nargs="+")
ap.add_argument("--saida", required=True)
ap.add_argument("--titulo", default="")
ap.add_argument("--correcoes")
ap.add_argument("--bloco", type=float, default=20.0)
ap.add_argument("--offset", type=float, default=0.0)
a = ap.parse_args()
cor = json.load(open(a.correcoes)) if a.correcoes else {}
saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)


def hms(t, ms=False):
    t = max(0.0, t)
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",") if ms else f"{int(h):02d}:{int(m):02d}:{int(s):02d}"


def limpa(txt):
    txt = re.sub(r"<[^>]+>", "", txt).strip()
    for errado, certo in cor.items():
        txt = re.sub(rf"\b{re.escape(errado)}\b", certo, txt)
    return re.sub(r"\s+", " ", txt)


for arq in map(Path, a.jsons):
    d = json.loads(arq.read_text())
    segs = [dict(s, start=s["start"] + a.offset, end=s["end"] + a.offset, text=limpa(s["text"]))
            for s in d["segments"] if s["text"].strip()]
    pausas = [(x + a.offset, y + a.offset) for x, y in d.get("pausas", []) if y - x >= 60]
    eventos = [("fala", s["start"], s) for s in segs] + [("pausa", x, (x, y)) for x, y in pausas]
    eventos.sort(key=lambda e: e[1])

    linhas = [f"# {a.titulo or arq.stem}", "",
              "Transcrição automática revisada. Os tempos [hh:mm:ss] são da gravação.", ""]
    bloco, ini, fim = [], None, None

    def fecha():
        if bloco:
            linhas.append(f"[{hms(ini)} - {hms(fim)}] {' '.join(bloco)}")
            linhas.append("")

    for tipo, t, s in eventos:
        if tipo == "pausa":
            fecha(); bloco, ini = [], None
            x, y = s
            linhas += [f"[PAUSA / SEM FALA {hms(x)} - {hms(y)} ({(y - x)/60:.0f} min)]", ""]
            continue
        if ini is None:
            ini = s["start"]
        bloco.append(s["text"]); fim = s["end"]
        if fim - ini >= a.bloco and re.search(r"[.!?…]$", s["text"]):
            fecha(); bloco, ini = [], None
    fecha()
    (saida / f"{arq.stem}.txt").write_text("\n".join(linhas), encoding="utf-8")

    srt = []
    for i, s in enumerate(segs, 1):
        srt += [str(i), f"{hms(s['start'], True)} --> {hms(s['end'], True)}", s["text"], ""]
    (saida / f"{arq.stem}.srt").write_text("\n".join(srt), encoding="utf-8")
    print(f"{arq.stem}: {len(segs)} falas, {len(pausas)} pausas longas -> {saida}")
