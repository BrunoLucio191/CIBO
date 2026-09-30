#!/usr/bin/env python3
"""Baixa a thumb de cada vídeo de um canal do YouTube na maior resolução pública.

Uso: python3 baixar_thumbs.py URL_DO_CANAL_OU_PLAYLIST PASTA [--pular N] [--max N]
  --pular N  ignora os N primeiros vídeos da lista (mais recentes), ex.: "com exceção do primeiro".

Tenta maxresdefault (1280x720), depois sddefault e hqdefault. O YouTube não publica o arquivo
original enviado (ex.: 1920x1080): esse só sai pelo YouTube Studio, logado como admin.
Nome do arquivo: "NN - titulo.jpg", na ordem do canal.
"""
import argparse, json, re, subprocess, sys, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("url")
ap.add_argument("pasta")
ap.add_argument("--pular", type=int, default=0)
ap.add_argument("--max", type=int, default=0, help="baixa só os N primeiros depois do --pular")
a = ap.parse_args()
url = a.url.rstrip("/")
if "/@" in url and not re.search(r"/(videos|streams|shorts)$", url):
    url += "/videos"
out = subprocess.run(["yt-dlp", "--flat-playlist", "-J", "--extractor-args", "youtube:lang=pt", url], capture_output=True, text=True)
if out.returncode:
    sys.exit(out.stderr[-800:])
itens = [e for e in json.loads(out.stdout).get("entries", []) if e.get("id")][a.pular:]
if a.max:
    itens = itens[:a.max]
pasta = Path(a.pasta)
pasta.mkdir(parents=True, exist_ok=True)
for n, e in enumerate(itens, 1 + a.pular):
    titulo = re.sub(r'[\\/:*?"<>|]', "", e.get("title") or e["id"])[:90].strip()
    destino = pasta / f"{n:02d} - {titulo}.jpg"
    for q in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            dados = urllib.request.urlopen(f"https://i.ytimg.com/vi/{e['id']}/{q}.jpg", timeout=30).read()
        except Exception:
            continue
        if len(dados) > 5000:  # o placeholder cinza de "sem maxres" tem ~1 KB
            destino.write_bytes(dados)
            print(f"{destino.name}  ({q})")
            break
    else:
        print(f"FALHOU {e['id']} {titulo}")
