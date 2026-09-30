#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transicoes de film burn vermelho da Malu -> <work>/burntrack.mov (o render.py faz o blend screen, como no original).

Uso: python3 burn.py job.json   (o render.py chama no prep quando o job tem "burn_events")

job["burn_events"] = [{"t": corte (tempo editado), "burn": "B9"}]: o pico de luz do burn cai exatamente no corte e
esconde a troca de layout (saida de tela dividida/card/tela cheia, entrada de tela cheia). Pedido do usuario: "evite
cortes secos onde obviamente caberia uma transicao, deixa o video feio e amador".
Fonte: o arquivo de film burn do usuario (o mesmo que a fernanda-produto usa para os whooshes). Os burns sao manchas de
luz sem forma, entao o quadro 16:9 e esticado para 9:16 inteiro (nao corta a luz). O SOM de cada burn vai para a
trilha de SFX pelo audio.py (evento com "src"), separado da voz.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
job = json.load(open(sys.argv[1]))
sys.path.insert(0, job.get("engine_scripts_fernanda", os.path.expanduser("~/.claude/skills/fernanda-produto/scripts")))
from timeline import duration

SRC = job.get("burn_src", os.path.expanduser("~/.claude/skills/fernanda-produto/assets/film_burn_transitions_sfx_source.mp4"))
# pico de luz de cada burn no arquivo (medido: luminancia a 10 fps); o som do arquivo ja vem sincronizado com a luz
BURNS = {"B1": 6.10, "B4": 10.00, "B6": 13.40, "B7": 14.60, "B9": 19.85, "B10": 21.40, "B12": 24.45, "B13": 25.65}
PRE, POST = 0.45, 0.50
D = duration(job); W = job["work"]


def events():
    return sorted(job.get("burn_events", []), key=lambda e: e["t"])


if __name__ == "__main__":
    ev = events()
    ins, f = "", f"color=black:s=1080x1920:r=30000/1001:d={D},format=gbrp[y];"
    prev = "y"
    for i, e in enumerate(ev):
        pk = BURNS[e["burn"]]; a = pk - PRE; start = max(0.0, e["t"] - PRE)
        ins += f'-ss {a:.3f} -t {PRE + POST:.3f} -i "{SRC}" '
        f += (f"[{i}:v]fps=30000/1001,scale=1080:1920:flags=bicubic,setsar=1,format=gbrp,"
              f"tpad=start_mode=add:start_duration={start:.3f}:color=black,tpad=stop_mode=add:stop_duration={D + 2}:color=black,"
              f"trim=duration={D}[x{i}];[{prev}][x{i}]blend=all_mode=screen[y{i}];")
        prev = f"y{i}"
    f += f"[{prev}]format=yuv422p10le[out]"
    subprocess.run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[out]" -c:v prores_videotoolbox -profile:v proxy '
                   f'"{W}/burntrack.mov"', shell=True, check=True)
    print(f"burntrack.mov: {len(ev)} burns vermelhos em " + ", ".join(f"{e['t']:.2f}s ({e['burn']})" for e in ev))
