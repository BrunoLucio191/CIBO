# -*- coding: utf-8 -*-
"""Config modular (padrao da Malu + job["kinetic"] + <work>/kinetic.json), caminhos e texto na tela.

Adaptado do kinetic do Bombordo (a skill de la nao e alterada). JSON em vez de YAML: roda no python3 do sistema,
o mesmo do render.py, sem dependencia nova.
"""
import copy, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
SKILL = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(job):
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    cfg = deep_merge(cfg, job.get("kinetic") or {})
    local = os.path.join(job["work"], "kinetic.json")
    if os.path.exists(local):
        cfg = deep_merge(cfg, json.load(open(local, encoding="utf-8")))
    for k in ("font", "font_highlight"):
        if not os.path.isabs(cfg[k]):
            cfg[k] = os.path.join(SKILL, "assets", "fonts", cfg[k])
    return cfg


def fern_path(job):
    p = job.get("engine_scripts_fernanda", os.path.expanduser("~/.claude/skills/fernanda-produto/scripts"))
    if p not in sys.path: sys.path.insert(0, p)
    return p


def hex_rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9%$]", "", w)


# Pontuacao na tela (regra do usuario): sai virgula, ponto, aspas, dois-pontos, ponto e virgula, reticencias,
# parenteses e travessao solto; ficam "?" e "!". Nunca sai: hifen DENTRO da palavra (Turi-Ita), acento, numero,
# "%" e "R$". So a borda da palavra e limpa; o miolo nunca e tocado.
_EDGE = ".,;:…\"“”'‘’«»()[]—–-"


def display(raw):
    w = raw.strip()
    tail = ""
    while w and w[-1] in "?!" + _EDGE:
        if w[-1] in "?!": tail = w[-1] + tail
        w = w[:-1]
    while w and w[0] in _EDGE:
        w = w[1:]
    if tail:
        tail = ("?" if "?" in tail else "") + ("!" if "!" in tail else "")
    return w + tail


def kdir(work):
    d = os.path.join(work, "kinetic"); os.makedirs(d, exist_ok=True); return d


def jload(p): return json.load(open(p, encoding="utf-8"))


def jsave(obj, p): json.dump(obj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
