# -*- coding: utf-8 -*-
"""Etapa 2 — blocos de 1 a 4 palavras e destaques (adaptado do segment.py do Bombordo).

Regras do Bombordo que ficam: quebra na pontuacao de frase e na pausa; nunca termina bloco em artigo/preposicao/
conjuncao; no maximo max_words / max_chars; bloco-relampago funde com o vizinho; destaque aparece sozinho, como
unidade, com a palavra funcional antes dele em corpo pequeno por cima; rodizio de presets (queda vertical abre frase
nova depois de pausa; o mesmo preset de destaque nunca duas vezes seguidas).

Da Malu:
- as quebras que o editor fez a mao (bloco e linha do captions.json) sao fronteiras duras;
- dentro de cada trecho entre quebras, os pontos de corte sao escolhidos pelo conjunto (programacao dinamica), nao
  pelo enchimento guloso do Bombordo, que deixava "preso" e "dias" sozinhos e separava "40 | dias". Nunca termina
  bloco em palavra funcional, "nao" ou demonstrativo, nunca separa numero da unidade, evita palavra sozinha e
  prefere blocos equilibrados;
- "ne" sozinho e bloco-relampago (< 0,35 s) juntam com o vizinho do mesmo bloco da mao;
- destaques escolhidos pelo sentido (config "highlights", em ordem de fala, "frase#2" = segunda ocorrencia) ou, sem
  lista, a primeira ocorrencia de cada job["keywords"].
Saida: <work>/kinetic/blocks.json (editavel: mova palavras, troque hl/small/preset e rode so a camada).
"""
import os, re
from common import norm, kdir, jload, jsave

FUNC = set("o a os as um uma uns umas de do da dos das em no na nos nas num numa por pelo pela pelos pelas à às "
           "para pra pro pros pras com sem sob sobre até ao aos e ou mas que se me te lhe lhes nem "
           "meu minha meus minhas seu sua seus suas nosso nossa teu tua".split())
STICKY = FUNC | set("não esse essa esses essas este esta estes estas aquele aquela aqueles aquelas".split())
UNITS = set("anos ano % por cento mil milhoes milhao dias dia meses mes semanas semana horas hora minutos "
            "vezes reais gramas grama kg ml litros litro colheres colher capsulas".split())
TAGS = set("né ne tá ta viu sabe".split())
# vao em corpo pequeno por cima do destaque: funcionais, demonstrativos e intensificadores ("muito intoxicada")
LEAD = FUNC | set("esse essa esses essas este esta estes estas muito muita bem tão tao super".split())
PUNCT_END = re.compile(r"[.!?;:…][\"”’»)]*$")


def low(w): return re.sub(r"[^\wà-ÿ%$-]", "", w.lower())
def is_func(w): return low(w["w"]) in FUNC
def sticky(w): return low(w["w"]) in STICKY
def is_num(w): return bool(re.search(r"\d", w["w"]))
def is_lead(w): return low(w["w"]) in LEAD


def runs(words, cfg, unit_of):
    """Trechos entre quebras duras/virgulas; cada destaque (com a palavra funcional antes) vira trecho proprio."""
    sg = cfg["segmentation"]; out = []; cur = []
    for i, w in enumerate(words):
        nxt = words[i + 1] if i + 1 < len(words) else None
        cur.append(i)
        gap = (nxt["s"] - w["e"]) if nxt else 9
        hand = nxt is None or nxt["blk"] != w["blk"] or nxt["line"] != w["line"]
        brk = hand or PUNCT_END.search(w["w"]) or gap > sg["pause_break"] or w["w"].rstrip("\"”’»)").endswith(",")
        if nxt is not None and not brk and i + 1 in unit_of and i not in unit_of:
            brk = True                                   # destaque comeca: fecha o trecho antes
        if i in unit_of and (nxt is None or unit_of.get(i + 1) != unit_of[i]):
            brk = True                                   # destaque termina
        if brk:
            out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def chunk(run, words, cfg):
    """Melhor divisao de um trecho em blocos (programacao dinamica)."""
    sg = cfg["segmentation"]; n = len(run)
    txt = lambda a, b: " ".join(words[run[k]]["d"] for k in range(a, b))

    def cost(a, b):
        L = b - a; chars = len(txt(a, b))
        if L > 1 and (L > sg["max_words"] or chars > sg["max_chars"]): return None
        if b < n:
            last, nxt = words[run[b - 1]], words[run[b]]
            if sticky(last): return None                 # "a | gente", "nao | tem", "esse | desconforto"
            if is_num(last) and low(nxt["w"]) in UNITS: return None   # "40 | dias"
        c = 1.0 + (3.0 if L == 1 and n > 1 else 0.0)
        return c + abs(chars - 14) / 10.0
    best = [0.0] + [None] * n; back = [0] * (n + 1)
    for b in range(1, n + 1):
        for a in range(max(0, b - sg["max_words"] - 1), b):
            if best[a] is None: continue
            c = cost(a, b)
            if c is None: continue
            if best[b] is None or best[a] + c < best[b]: best[b] = best[a] + c; back[b] = a
    if best[n] is None:                                  # nada cabe: um bloco so (o layout quebra em 2 linhas)
        return [run]
    cuts, b = [], n
    while b > 0: cuts.append((back[b], b)); b = back[b]
    return [[run[k] for k in range(a, b)] for a, b in reversed(cuts)]


def highlight_units(words, cfg, job):
    nw = [norm(w["w"]) for w in words]; units = []
    spec = cfg.get("highlights")
    if spec:
        pos = 0
        for ph in spec:
            occ = 1
            if "#" in ph: ph, occ = ph.split("#")[0], int(ph.split("#")[1])
            toks = [norm(x) for x in ph.split() if norm(x)]
            hits = [i for i in range(pos, len(nw) - len(toks) + 1) if nw[i:i + len(toks)] == toks]
            if len(hits) >= occ:
                i = hits[occ - 1]; units.append((i, i + len(toks) - 1)); pos = i + len(toks)
            else:
                print(f'   aviso: destaque "{ph}" nao encontrado em ordem no texto', flush=True)
    else:
        for k in job.get("keywords", []):
            i = next((i for i, n in enumerate(nw) if n == norm(k)), None)
            if i is not None: units.append((i, i))
        units.sort()
    return units


def build(job, cfg):
    W = jload(os.path.join(kdir(job["work"]), "words.json"))["words"]
    units = highlight_units(W, cfg, job)
    unit_of = {}
    for u, (a0, b0) in enumerate(units):
        a = a0                                           # palavra funcional antes do destaque vai pequena com ele
        while a > 0 and a0 - a < 2 and is_lead(W[a - 1]) and W[a - 1]["line"] == W[a0]["line"] \
                and W[a - 1]["blk"] == W[a0]["blk"] and (a - 1) not in unit_of:
            a -= 1
        for i in range(a, b0 + 1): unit_of[i] = u
    final = []
    for r in runs(W, cfg, unit_of):
        if r[0] in unit_of:
            u = unit_of[r[0]]; a0 = units[u][0]
            final.append(dict(kind="highlight", idx=r, small=[i for i in r if i < a0]))
        else:
            final += [dict(kind="normal", idx=c) for c in chunk(r, W, cfg)]
    sg = cfg["segmentation"]; mx = sg["max_words"] + 1
    blk_of = lambda b: W[b["idx"][0]]["blk"]
    fits2 = lambda idx: len(idx) <= 2 * sg["max_words"] and len(" ".join(W[i]["d"] for i in idx)) <= 2 * sg["max_chars"]
    same_line = lambda i, j: W[i]["blk"] == W[j]["blk"] and W[i]["line"] == W[j]["line"]
    merged = []
    for n, b in enumerate(final):
        nxt = final[n + 1] if n + 1 < len(final) else None
        prv = merged[-1] if merged else None
        if b["kind"] == "normal":
            span = W[nxt["idx"][0]]["s"] - W[b["idx"][0]]["s"] if nxt is not None else 9
            single_tag = len(b["idx"]) == 1 and low(W[b["idx"][0]]["w"]) in TAGS
            if single_tag and prv and prv["kind"] == "normal" and blk_of(prv) == blk_of(b) and fits2(prv["idx"] + b["idx"]):
                prv["idx"] += b["idx"]; continue
            # palavra solta e curta logo antes do destaque, na mesma linha: vai pequena por cima dele ("sao mais grossas")
            if (nxt is not None and nxt["kind"] == "highlight" and len(b["idx"]) == 1 and span < 0.6
                    and same_line(b["idx"][0], nxt["idx"][0]) and len(nxt.get("small", [])) < 2):
                nxt["idx"] = b["idx"] + nxt["idx"]; nxt["small"] = b["idx"] + nxt.get("small", []); continue
            if span < sg["flash"]:                       # relampago: junta com o vizinho do mesmo bloco da mao
                if nxt["kind"] == "normal" and blk_of(nxt) == blk_of(b) and fits2(b["idx"] + nxt["idx"]):
                    nxt["idx"] = b["idx"] + nxt["idx"]; continue
                if (nxt["kind"] == "highlight" and same_line(b["idx"][-1], nxt["idx"][0])
                        and len(nxt.get("small", [])) + len(b["idx"]) <= 3):   # "Tanto" ficava 0,04 s sozinho
                    nxt["idx"] = b["idx"] + nxt["idx"]; nxt["small"] = b["idx"] + nxt.get("small", []); continue
                if prv and prv["kind"] == "normal" and blk_of(prv) == blk_of(b) and fits2(prv["idx"] + b["idx"]):
                    prv["idx"] += b["idx"]; continue
        merged.append(b)
    out = []; last_norm = None; hl_p = cfg["presets"]["highlight"]; hc = 0
    for n, b in enumerate(merged):
        ws = [dict(w=W[i]["d"], raw=W[i]["w"], s=W[i]["s"], e=W[i]["e"], blk=W[i]["blk"], line=W[i]["line"],
                   small=(i in b.get("small", [])), hl=(b["kind"] == "highlight" and i not in b.get("small", [])))
              for i in b["idx"]]
        if b["kind"] == "highlight":
            preset = hl_p[hc % len(hl_p)]; hc += 1
        else:
            prev_end = out[-1]["words"][-1]["e"] if out else -9
            prev_raw = out[-1]["words"][-1]["raw"] if out else "."
            new_sentence = PUNCT_END.search(prev_raw) and ws[0]["s"] - prev_end > 0.35
            preset = "slide_blur"
            if new_sentence and last_norm != "drop_blur": preset = "drop_blur"
            elif len(ws) >= 3 and last_norm != "mask_reveal" and n % 4 == 3: preset = "mask_reveal"
            last_norm = preset
        out.append(dict(id=n, kind=b["kind"], preset=preset, words=ws))
    nh = sum(1 for b in out if b["kind"] == "highlight")
    res = dict(note="edite: mova palavras entre blocos, troque hl/small true/false e preset em " + str(cfg["presets"]),
               blocks=out)
    p = os.path.join(kdir(job["work"]), "blocks.json"); jsave(res, p)
    print(f"blocks: {len(out)} blocos, {nh} destaques -> {p}", flush=True)
    return res
