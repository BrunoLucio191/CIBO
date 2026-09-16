#!/usr/bin/env python3
"""Trilha de enquadramento 9:16, delegando a analise para a skill do Bombordo.

O face_crop.py da skill bombordo-boreste resolve o problema certo: ele acha os
cortes reais de camera da fonte e usa UMA mediana de rosto por plano, em vez de
perseguir o rosto quadro a quadro. Perseguir causava dois defeitos que o Bruno
apontou: micro-tremor no plano parado e, pior, saltos laterais no meio de um
plano continuo, que na tela leem como flash de troca de camera.

Aqui so traduzimos o resultado para o formato sendcmd que o render usa.

Uso: reframe.py <video> <ini> <fim> <saida.sendcmd> [--preview arquivo.png]
"""
import importlib.util
import os
import sys

SKILL = os.path.expanduser("~/.claude/skills/bombordo-boreste/scripts/face_crop.py")
LARG_CROP = 608
LIMIAR_CENA = 18.0        # mesmo default da skill


def carrega_skill():
    spec = importlib.util.spec_from_file_location("face_crop", SKILL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    video, ini, fim, saida = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    fc = carrega_skill()
    res = fc.analyse(video, [(ini, fim)], crop_width=LARG_CROP,
                     scene_threshold=LIMIAR_CENA)

    xmax = res["width"] - LARG_CROP
    linhas, anterior = [], None
    for plano in res["shots"]:
        x = int(round(plano["cropx"] * xmax))
        if x == anterior:
            continue
        t = max(plano["start"] - ini, 0.0)
        linhas.append(f"{t:.3f} crop x {x};")
        anterior = x
    if not linhas:
        linhas = [f"0.000 crop x {xmax // 2};"]
    open(saida, "w").write("\n".join(linhas) + "\n")

    if "--preview" in sys.argv:
        fc.preview(res, sys.argv[sys.argv.index("--preview") + 1])

    print(f"{saida}\tplanos={len(res['shots'])}\tcomandos={len(linhas)}\t"
          f"x=[{min(int(p['cropx']*xmax) for p in res['shots'])},"
          f"{max(int(p['cropx']*xmax) for p in res['shots'])}]")


if __name__ == "__main__":
    main()
