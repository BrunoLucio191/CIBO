#!/usr/bin/env python3
"""Acha candidatos a bastidor/pausa/retake na transcrição e mostra o contexto.

Uso:
  python3 achar_bastidores.py DIR/segmentos.tsv [--contexto 25] [--janela A-B ...]

Sem --janela: lista cada ocorrência de palavra-chave com ~25 s de contexto,
agrupando ocorrências próximas. Com --janela 17:30-22:10 (ou segundos): imprime
o texto corrido daquele intervalo, para ler a borda de um corte.

As palavras-chave só APONTAM onde olhar. Quem decide é a leitura do contexto:
"corte" pode ser conteúdo ("esses cortes rendem muito"), e bastidor muitas vezes
não tem palavra-chave nenhuma (conversa de voto, agenda, futebol).
"""
import argparse, re

KW = re.compile(
    r"\bpaus|\bcorta\b|\bcorte\b|\bcortar\b|tira (isso|essa|esse)|\bexclu|\bapaga|esquece isso|"
    r"fora do ar|não (grava|publica|posta|coloca|põe|bota)|deixa quiet|\boff\b|desliga|tá gravando|"
    r"recomeç|regrav|refaz|de novo|faz aí|vou reformular|reformula|pode ir|pode continuar|"
    r"um, dois, três|\b1, 2, 3\b|no (número )?3|peraí|espera aí|calma aí|segura aí|"
    r"aí tu (fala|começa|entra)|tu fala assim|contextualiza|enquadramento|tá saindo|"
    r"reavalia|bloco|bate.?bola|esse corte|ficou bom",
    re.I)


def ts(x):
    if ":" in x:
        p = [float(v) for v in x.split(":")]
        return sum(v * 60 ** i for i, v in enumerate(reversed(p)))
    return float(x)


def fmt(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:04.1f}"


ap = argparse.ArgumentParser()
ap.add_argument("tsv")
ap.add_argument("--contexto", type=float, default=25)
ap.add_argument("--janela", nargs="*")
a = ap.parse_args()
L = []
for linha in open(a.tsv):
    s, e, t = linha.rstrip("\n").split("\t", 2)
    L.append((float(s), float(e), t))

if a.janela:
    for j in a.janela:
        x, y = (ts(v) for v in j.split("-"))
        print(f"== {fmt(x)} – {fmt(y)}")
        print(" ".join(f"[{fmt(s)}] {t}" for s, e, t in L if x <= s <= y), "\n")
    raise SystemExit

hits = [s for s, e, t in L if KW.search(t)]
grupos = []
for h in hits:
    if grupos and h - grupos[-1][1] < a.contexto:
        grupos[-1][1] = h
    else:
        grupos.append([h, h])
for x, y in grupos:
    x0, y0 = x - a.contexto / 2, y + a.contexto / 2
    print(f"== {fmt(x)} – {fmt(y)}")
    print(" ".join((f"[{fmt(s)}] >>{t}<<" if KW.search(t) else f"[{fmt(s)}] {t}")
                   for s, e, t in L if x0 <= s <= y0), "\n")

# Alucinação do Whisper ("tá tá tá…", texto repetido) costuma marcar falha técnica/ruído
for s, e, t in L:
    w = t.split()
    if len(w) > 12 and len(set(w)) <= 3:
        print(f"!! possível falha técnica/alucinação em {fmt(s)}–{fmt(e)}: {t[:60]}…")
