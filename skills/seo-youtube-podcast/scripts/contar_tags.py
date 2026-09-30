#!/usr/bin/env python3
"""Conta as tags do YouTube como o YouTube conta (limite 500).

O YouTube soma os caracteres das tags e das vírgulas e acrescenta 2 para cada tag com espaço
(ele a guarda entre aspas). Conferido em set/2026: 460 caracteres de texto com 20 tags de
várias palavras deram exatamente 500 no Studio.

Uso:
  python3 contar_tags.py "tag um,tag dois,tag"      # ou
  python3 contar_tags.py -f tags.txt [--limite 500]
Sai com código 1 se passar do limite, e diz quais tags cortar do fim.
"""
import argparse, sys

ap = argparse.ArgumentParser()
ap.add_argument("tags", nargs="?")
ap.add_argument("-f", "--arquivo")
ap.add_argument("--limite", type=int, default=500)
a = ap.parse_args()
bruto = open(a.arquivo).read() if a.arquivo else (a.tags or sys.stdin.read())
tags = [t.strip() for t in bruto.replace("\n", ",").split(",") if t.strip()]


def custo(ts):
    return len(",".join(ts)) + 2 * sum(" " in t for t in ts)


vistos, dup = set(), []
for t in tags:
    k = t.lower()
    if k in vistos:
        dup.append(t)
    vistos.add(k)
total = custo(tags)
print(f"{len(tags)} tags | texto {len(','.join(tags))} | contagem do YouTube {total}/{a.limite}")
if dup:
    print("repetidas:", ", ".join(dup))
if total > a.limite:
    cortar = []
    while tags and custo(tags) > a.limite:
        cortar.insert(0, tags.pop())
    print("passa do limite; tire do fim:", ", ".join(cortar))
    sys.exit(1)
print(f"sobram {a.limite - total} caracteres")
