#!/usr/bin/env python3
"""Transforma a transcricao crua na transcricao de trabalho, de forma reproduzivel.

Tres defeitos da transcricao de producao, todos achados pela verificacao cruzada
com um modelo mais forte:

1. Nos limites de 10 minutos o transcritor processou em blocos com sobreposicao
   e repetiu palavras ("Voce voce comenta", "queriam taxar a a cada 20 reais").
   Isso e artefato, nao fala; as repeticoes de verdade do episodio ficam.
2. Onde os dois falam por cima, varias palavras saem com o mesmo timestamp e
   duracao zero. Elas viram um bloco de legenda impossivel de ler. Aqui o tempo
   e distribuido no vao disponivel e a palavra fica marcada com "reparado",
   para o montador de legenda saber que aquele bloco veio de fala sobreposta.
3. Um trecho de dois segundos ficou de fora da transcricao (o modelo forte ouviu
   "la em casa, pouco tempo, ne, e tem"). Ele e reinserido com tempo repartido
   por numero de caracteres.

Alem disso, o transcritor formalizou oralidade em tres pontos ("estou" no lugar
de "to", "para" no lugar de "pra"). A legenda tem que dizer o que foi dito.

Uso: preparar_transcricao.py <cru.json> <saida.json>
"""
import json
import sys

LIMITES = (600, 1200, 1800, 2400, 3000, 3600)
FALA_PERDIDA = [(602.26, 604.28, "lá em casa, pouco tempo, né, e tem várias")]
ORALIDADE = {1214.52: ("estou", "tô"), 1215.94: ("para", "pra"),
             1218.52: ("para", "pra")}


def nu(w):
    return w["word"].strip().lower().strip(".,;:!?")


def tira_duplicatas_de_bloco(p):
    fora = set()
    for b in LIMITES:
        for i, w in enumerate(p):
            if abs(w["start"] - b) >= 0.08:
                continue
            if i > 0 and nu(p[i]) == nu(p[i - 1]):
                fora.add(i)
            elif i > 1 and i + 1 < len(p) and \
                    [nu(p[i]), nu(p[i + 1])] == [nu(p[i - 2]), nu(p[i - 1])]:
                fora.update({i, i + 1})
    return [w for i, w in enumerate(p) if i not in fora], len(fora)


def repara_tempo_zero(p):
    n = 0
    i = 0
    while i < len(p):
        j = i
        while j + 1 < len(p) and p[j + 1]["start"] <= p[i]["start"] + 1e-6:
            j += 1
        if j > i:
            ini = p[i]["start"]
            fim = p[j + 1]["start"] if j + 1 < len(p) else p[j]["end"]
            fim = max(fim, ini + 0.12 * (j - i + 1))
            passo = (fim - ini) / (j - i + 1)
            for k in range(i, j + 1):
                p[k]["start"] = round(ini + passo * (k - i), 3)
                p[k]["end"] = round(ini + passo * (k - i + 1), 3)
                p[k]["reparado"] = True
            n += j - i + 1
        i = j + 1
    return p, n


def main():
    cru, saida = sys.argv[1], sys.argv[2]
    p = json.load(open(cru))
    p, n_dup = tira_duplicatas_de_bloco(p)
    p, n_rep = repara_tempo_zero(p)

    n_ins = 0
    for a, b, texto in FALA_PERDIDA:
        p = [w for w in p if not (a - 1e-6 <= w["start"] < b)]
        palavras = texto.split()
        tot = sum(len(x) for x in palavras)
        t = a
        for x in palavras:
            d = (b - a) * len(x) / tot
            p.append({"start": round(t, 3), "end": round(t + d, 3), "word": " " + x})
            t += d
            n_ins += 1
    p.sort(key=lambda w: w["start"])

    n_oral = 0
    for w in p:
        for t0, (antes, depois) in ORALIDADE.items():
            if abs(w["start"] - t0) < 0.35 and w["word"].strip().lower() == antes:
                # preserva a caixa: "Para" no inicio de frase vira "Pra"
                novo = depois.capitalize() if w["word"].strip()[0].isupper() else depois
                w["word"] = " " + novo
                n_oral += 1

    json.dump(p, open(saida, "w"), ensure_ascii=False)
    print(f"{saida}\tduplicatas_removidas={n_dup}\ttempos_reparados={n_rep}"
          f"\tpalavras_reinseridas={n_ins}\toralidade={n_oral}\ttotal={len(p)}")


if __name__ == "__main__":
    main()
