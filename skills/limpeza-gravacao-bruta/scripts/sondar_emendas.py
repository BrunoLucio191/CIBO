#!/usr/bin/env python3
"""Mede o sinal em volta de cada ponto de corte e sugere o ponto exato.

Uso (Python do mlx-whisper):
  ~/.local/share/uv/tools/mlx-whisper/bin/python sondar_emendas.py DIR/audio16k.wav cortes.json

cortes.json: lista [[inicio_corte, fim_corte], ...] em segundos do original
(o trecho entre eles SAI). Use null no fim do último corte para "até o final".

Para cada borda imprime:
  - palavras com tempo (Whisper word_timestamps) em ±6 s
  - perfil de 20 ms: V = voz (energia + periodicidade), b = som sem voz
    (respiração, suspiro, chiado, consoante surda), . = silêncio
  - sugestão: SAÍDA = fim da última voz + folga até o próximo vale;
    VOLTA = início da voz da primeira palavra, pulando respiração/suspiro

Por que não confiar só no Whisper: nesta pipeline o tempo por palavra errou
0,3–0,5 s em vários pontos (ex.: "e" marcado em 465.62, voz real em 466.00) e o
tempo por frase erra até 1 s. Suspiro de 0,5–0,7 s antes da fala é "b" contínuo
em −23…−30 dB colado no primeiro "V".
"""
import json, subprocess, sys

import numpy as np
import mlx_whisper

SR, FR = 16000, 320  # 20 ms


def carregar(wav, s, d):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, s):.3f}", "-t", f"{d:.3f}", "-i", wav,
                          "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def perfil(a, s):
    out = []
    for i in range(0, len(a) - FR, FR):
        x = a[i:i + FR]
        db = 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
        x0 = x - x.mean()
        ac = np.correlate(x0, x0, "full")[FR - 1:]
        v = ac[40:200].max() / (ac[0] + 1e-9) if ac[0] > 0 else 0  # periodicidade 80–400 Hz
        tag = "V" if (db > -35 and v > 0.5) else ("b" if db > -45 else ".")
        out.append((s + i / SR, db, tag))
    return out


def sug_saida(P, t):
    """Dois candidatos: CURTO = primeiro vale de 40 ms (< -35 dB) depois da última voz até t;
    LONGO = logo antes da próxima fala forte. O sinal não separa fim de palavra surda
    ("-so" de "sucesso", 0,25 s em -27 dB) de respiração/suspiro de quem vai falar, então
    main() transcreve o trecho mantido terminando em cada candidato para decidir."""
    ult = max((p for p in P if p[2] == "V" and p[0] <= t + 0.1), key=lambda p: p[0], default=None)
    if not ult:
        return t, t
    curto = next((round(P[i][0] + 0.02, 2) for i in range(len(P) - 1)
                  if P[i][0] > ult[0] and P[i][1] < -35 and P[i + 1][1] < -35), round(ult[0] + 0.12, 2))
    longo = curto
    for i in range(len(P) - 2):
        if P[i][0] > curto and all(P[i + k][1] > -20 for k in range(3)):
            longo = round(P[i][0] - 0.05, 2)
            break
    return curto, longo


def sug_volta(P, t):
    # primeira fala FORTE e sustentada (3 quadros > -20 dB, ao menos um com voz) a partir de
    # 0,1 s antes do ponto (ponha t DEPOIS de direção/gaguejada: a escolha da palavra é editorial). Suspiro/respiração fica em -20...-30 dB e não dispara. Depois recua
    # no máximo 40 ms sobre quadros > -27 dB (ataque de consoante: "C" de "Claro").
    ini = None
    for i in range(len(P) - 2):
        if P[i][0] >= t - 0.1 and all(P[i + k][1] > -20 for k in range(3)) and any(P[i + k][2] == "V" for k in range(3)):
            ini = i
            break
    if ini is None:
        return t
    j = ini
    while j > 0 and P[j - 1][1] > -27 and P[ini][0] - P[j - 1][0] <= 0.04:
        j -= 1
    return round(P[j][0] - 0.02, 2)


def main():
    wav, cj = sys.argv[1], sys.argv[2]
    cortes = json.load(open(cj))
    for ini, fim in cortes:
        for tipo, t in (("SAÍDA", ini), ("VOLTA", fim)):
            if t is None or t <= 0:
                continue
            s = max(0, t - 6)
            a = carregar(wav, s, 12)
            r = mlx_whisper.transcribe(a, path_or_hf_repo="mlx-community/whisper-large-v3-turbo", language="pt",
                                       word_timestamps=True, condition_on_previous_text=False)
            ws = [(s + w["start"], s + w["end"], w["word"].strip()) for g in r["segments"] for w in g.get("words", [])]
            P = perfil(carregar(wav, t - 1.2, 2.4), t - 1.2)
            linhas = []
            if tipo == "SAÍDA":
                curto, longo = sug_saida(P, t)
                # <= 0,3 s entre os candidatos: é o fim da própria palavra ("-so") -> LONGO (folga).
                # > 0,3 s: é respiração/suspiro de quem vai falar -> CURTO.
                sug = longo if longo - curto <= 0.3 else curto
                for nome, c in (("CURTO", curto), ("LONGO", longo)):
                    if nome == "LONGO" and longo == curto:
                        continue
                    tr = mlx_whisper.transcribe(carregar(wav, c - 3, 3), path_or_hf_repo="mlx-community/whisper-large-v3-turbo",
                                                language="pt", condition_on_previous_text=False)["text"].strip()
                    linhas.append(f"    {nome} {c:.2f}: termina em «…{tr[-60:]}»")
            else:
                sug = sug_volta(P, t)
            print(f"### {tipo} em {t:.2f}  → sugestão {sug:.2f}")
            for l in linhas:
                print(l)
            print("   ", " ".join(f"{w}[{a_:.2f}-{b_:.2f}]" for a_, b_, w in ws if abs(a_ - t) < 4))
            print("   ", "".join(p[2] for p in P), f"(de {t-1.2:.2f}, 20 ms/char)")
            print("   ", " ".join(f"{p[0]:.2f}:{p[1]:.0f}{p[2]}" for p in P if abs(p[0] - t) <= 0.6))
            print()


if __name__ == "__main__":
    main()
