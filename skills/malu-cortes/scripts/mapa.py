#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mapa de edicao (05_qa/<reel>_mapa_edicao.md) montado a partir do job: uma linha por evento, em tempo editado.

Uso: python3 mapa.py job.json SAIDA.md
Planos (nivel), movimentos de camera, referencias, graficos, destaques da legenda e SFX, com a conferencia de ritmo
(maior buraco sem evento, instantes com mais de 2 eventos de motion). A intencao de cada escolha vem do campo
"intencao" do item no job quando existir; senao, da regra da skill para aquele tipo de evento.
"""
import json, os, sys
job = json.load(open(sys.argv[1])); out = sys.argv[2]
sys.path.insert(0, job.get("engine_scripts_fernanda", os.path.expanduser("~/.claude/skills/fernanda-produto/scripts")))
from timeline import duration
D = duration(job); ev = []
NIV = {0: "N0 aberto", 1: "N1 médio", 2: "N2 fechado"}
acc = 0.0
for i, (s0, s1, k) in enumerate(job["shots"]):
    lv = job["shot_levels"][i]
    ev.append((round(acc, 2), "plano", NIV.get(lv, lv), "corte seco com troca de nível (jump cut escondido)")); acc += s1 - s0
for m in job.get("camera_moves", []):
    txt = {"punch": f"punch {m['amount']:.0%} em {m.get('in', 0.3)} s", "push": f"push-in lento {m['amount']:.0%} até {m['until']}",
           "breathe": f"respiro {m['amount']:.1%}"}[m["kind"]]
    why = {"punch": "ênfase/punchline, ancorado no rosto", "push": "ideia que cresce", "breathe": "nada fica 100% parado"}[m["kind"]]
    ev.append((m["t"], "câmera", txt, m.get("intencao", why)))
for r in job.get("malu_refs", []):
    if r["kind"] == "endbg": continue
    src = os.path.basename(r["file"]) if "file" in r else "insert do master (estante Turi-Ita)"
    ev.append((r["start"], "referência", f"{r['kind']} {r['start']:.2f}-{r['end']:.2f} · {src}", r.get("intencao", "imagem para a fala, entra e sai no corte ou em pausa")))
for g in job.get("graphics", []):
    ev.append((g["t"], "gráfico", f"{g['kind']} «{g.get('name', '')}»", g.get("intencao", {"title": "gancho com a frase mais forte dela",
               "callout": "a comparação/termo vira imagem", "number": "número grande 1-1,5 s", "endcard": "encerramento com o produto"}.get(g["kind"], ""))))
blocks = os.path.join(job["work"], "kinetic", "blocks.json")
if os.path.exists(blocks):
    for b in json.load(open(blocks))["blocks"]:
        if b["kind"] == "highlight":
            ev.append((round(b["words"][0]["s"], 2), "destaque", " ".join(w["w"] for w in b["words"]), "palavra-chave pelo sentido (SemiBold 1,3x)"))
for s in job.get("sfx_events", []):
    ev.append((s["t"], "SFX", s["sfx"], "sincronizado com o movimento; fora das consoantes"))
ev.sort(key=lambda e: e[0])
motion = sorted(t for t, k, *_ in ev if k in ("gráfico", "referência", "destaque") or (k == "câmera" and "respiro" not in _[0]))
vis = sorted({t for t, k, *_ in ev if k != "SFX"})
gap = max(b - a for a, b in zip([0.0] + vis, vis + [D]))
L = [f"# {job['name']} — mapa de edição", "", f"Duração {D:.2f} s · trilha: {job.get('music_source', {}).get('name', '-')}", "",
     "| Tempo | Tipo | Evento | Intenção |", "|---|---|---|---|"]
L += [f"| {t:.2f} | {k} | {e} | {w} |" for t, k, e, w in ev]
L += ["", "## Conferência de ritmo", f"- Maior trecho sem mudança visual: {gap:.2f} s (limite 5 s).",
      f"- SFX: {sum(1 for e in ev if e[1] == 'SFX')} em {D:.1f} s.",
      f"- Destaques: {sum(1 for e in ev if e[1] == 'destaque')}."]
open(out, "w").write("\n".join(L) + "\n"); print(f"mapa: {len(ev)} eventos, maior buraco {gap:.2f} s -> {out}")
