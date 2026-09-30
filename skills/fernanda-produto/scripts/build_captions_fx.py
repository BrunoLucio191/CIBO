"""Legenda por frase, colada no inicio real da fala (substitui os blocos picados de 1-3 palavras).

Uso: python3 build_captions_fx.py job.json AUD.wav WORDS.json CAPTIONS_TXT.json SAIDA.json [--xfade N]
  AUD.wav            voz editada (a mesma linha do tempo de WORDS.json)
  WORDS.json         Whisper com word_timestamps sobre AUD.wav
  CAPTIONS_TXT.json  legenda ja revisada (so o TEXTO e usado, na ordem): e a fonte das palavras certas
  --xfade N          se AUD.wav foi montado com acrossfade de N s por corte e o render nao usa, corrige os tempos

Por que: o usuario viu "cada palavra num tempo diferente" -- blocos de 1-3 palavras trocando a cada ~1 s, e
alguns entrando 0,3-0,8 s depois da fala porque o Whisper marca tarde a primeira palavra. Aqui:
- as palavras revisadas recebem os tempos do Whisper por alinhamento (difflib);
- um bloco por oracao (pontuacao), ate 44 caracteres em ate 2 linhas; curtas juntam, longas dividem equilibrado;
- o inicio de cada bloco e puxado para o onset real da fala (envelope de 10 ms), no maximo 0,8 s antes.
"""
import difflib, json, subprocess, sys, unicodedata
import numpy as np

sys.path.insert(0, __import__("os").path.dirname(__file__))
from timeline import load_job, segments

job = load_job(sys.argv[1])
AUD, WORDS, TXT, OUT = sys.argv[2:6]
XF = float(sys.argv[sys.argv.index("--xfade") + 1]) if "--xfade" in sys.argv else 0.0
MAX = 26
FUNC = {"o", "a", "os", "as", "um", "uma", "e", "de", "da", "do", "das", "dos", "na", "no", "numa", "com", "que", "sem",
        "em", "se", "por", "para", "pra", "essas", "esse", "sua", "seu", "nossa", "nosso", "ter", "é", "à", "já", "você",
        "mas", "ou", "ela", "ele", "tem", "muito", "mais", "não", "nao", "eu", "aí", "ai", "todo", "toda", "milhões", "milhoes", "voce", "e"}


def norm(s):
    s = unicodedata.normalize("NFD", s.strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip(".,!?:;\"'")


# palavras do Whisper (tempo de AUD) e palavras revisadas
wd = json.load(open(WORDS))
W = [(norm(w["word"]), w["start"], w["end"]) for s in wd["segments"] for w in s["words"] if norm(w["word"])]
R = [t for c in json.load(open(TXT)) for t in c["text"].split()]
sm = difflib.SequenceMatcher(a=[norm(t) for t in R], b=[w[0] for w in W], autojunk=False)
times = [None] * len(R)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
        for k in range(i2 - i1):
            times[i1 + k] = (W[j1 + k][1], W[j1 + k][2])
    elif tag == "replace":  # tamanhos diferentes: espalha o intervalo do Whisper pelas palavras revisadas
        a, b = W[j1][1], W[j2 - 1][2]
        for k in range(i2 - i1):
            times[i1 + k] = (a + (b - a) * k / (i2 - i1), a + (b - a) * (k + 1) / (i2 - i1))
for k in range(len(R)):  # palavras inseridas sem par: herdam o vizinho
    if times[k] is None:
        prev = times[k - 1] if k else (0.0, 0.0)
        times[k] = (prev[1], prev[1] + 0.2)

# envelope para achar o onset real
sr = 16000
x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", AUD, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                                 capture_output=True).stdout, np.int16).astype(float) / 32768
env = np.array([20 * np.log10(np.sqrt((x[i:i + 160] ** 2).mean()) + 1e-9) for i in range(0, len(x) - 160, 160)])
thr = np.percentile(env, 10) + 12


def onset(t):
    k0, k1 = int((t - 0.8) * 100), int((t + 0.1) * 100)
    for k in range(min(k1, len(env) - 1), max(k0, 12), -1):
        if env[k] >= thr and (env[k - 12:k] < thr).all():
            return k / 100 - 0.03
    return t - 0.05


# blocos por oracao: quebra na pontuacao, ate MAX2 caracteres (o fx_layer mostra em ate 2 linhas equilibradas);
# oracao curta junta com a seguinte; oracao longa divide em pedacos equilibrados sem terminar em palavra funcional
MAX2 = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 52
txt = lambda ws: " ".join(R[i] for i in ws)
clauses, cur = [], []
for i in range(len(R)):
    if cur and times[i][0] - times[cur[-1]][1] > 0.7:
        clauses.append(cur); cur = []
    cur.append(i)
    if R[i][-1] in ".?!,":
        clauses.append(cur); cur = []
if cur:
    clauses.append(cur)
merged = []
for c in clauses:
    if merged and len(txt(merged[-1])) < 22 and len(txt(merged[-1] + c)) <= MAX2 \
            and times[c[0]][0] - times[merged[-1][-1]][1] < 0.6 and R[merged[-1][-1]][-1] not in ".?!":
        merged[-1] = merged[-1] + c
    elif merged and len(txt(c)) < 10 and len(txt(merged[-1] + c)) <= MAX2 \
            and times[c[0]][0] - times[merged[-1][-1]][1] < 0.6 and R[merged[-1][-1]][-1] not in ".?!":
        merged[-1] = merged[-1] + c
    else:
        merged.append(c)


NOSPLIT_AFTER = {"carga", "maior", "teste", "metal"}   # "carga | iônica", "teste | microbiológico"...
BREAK_BEFORE = {"que", "porque", "onde", "e", "se", "para", "pra", "mas", "então", "entao", "quando", "com", "vai", "tem"}


def split(ws):
    """Divide uma oracao longa em pedacos equilibrados; prefere quebrar antes de conectivo e nunca depois de
    palavra funcional."""
    if len(txt(ws)) <= MAX2:
        return [ws]
    n = -(-len(txt(ws)) // MAX2)
    target = len(txt(ws)) / n
    best = None
    for k in range(1, len(ws)):
        if norm(R[ws[k - 1]]) in FUNC or R[ws[k - 1]].strip(".,").isdigit() or norm(R[ws[k - 1]]) in NOSPLIT_AFTER:
            continue
        d = abs(len(txt(ws[:k])) - target) - (6 if norm(R[ws[k]]) in BREAK_BEFORE else 0)
        if len(txt(ws[:k])) > MAX2 + 4 or len(txt(ws[k:])) > MAX2 * (n - 1) + 4:
            d += 50
        if best is None or d < best[0]:
            best = (d, k)
    k = best[1] if best else len(ws) // 2
    return split(ws[:k]) + split(ws[k:])


blocks = [p for c in merged for p in split(c)]
# bloco curto demais (< 10 caracteres ou terminando em palavra funcional) gruda no vizinho se couber;
# se ele fecha frase (. ? !) so pode grudar no ANTERIOR -- nunca juntar o fim de uma frase com o inicio da outra
changed = True
while changed:
    changed = False
    for k, b in enumerate(blocks):
        ends_sentence = R[b[-1]][-1] in ".?!"
        short = len(txt(b)) < 10 or (norm(R[b[-1]]) in FUNC and not ends_sentence)
        if not short:
            continue
        prev_ok = k > 0 and R[blocks[k - 1][-1]][-1] not in ".?!" and len(txt(blocks[k - 1] + b)) <= MAX2 + 6
        next_ok = k + 1 < len(blocks) and not ends_sentence and len(txt(b + blocks[k + 1])) <= MAX2 + 6
        if ends_sentence and prev_ok:
            blocks[k - 1:k + 1] = [blocks[k - 1] + b]; changed = True; break
        if next_ok:
            blocks[k:k + 2] = [b + blocks[k + 1]]; changed = True; break
        if prev_ok and len(txt(b)) < 10:
            blocks[k - 1:k + 1] = [blocks[k - 1] + b]; changed = True; break

# tempo AUD -> tempo do render (sem acrossfade)
bounds, acc = [], 0.0
for k, (a, b) in enumerate(segments(job)[:-1]):
    acc += b - a
    bounds.append(acc - XF * (k + 1))
shift = lambda t: round(t + XF * sum(1 for q in bounds if t >= q), 3)

caps = []
for bi, b in enumerate(blocks):
    w0 = times[b[0]][0]
    s = max(0.0, onset(w0))
    if caps and s < caps[-1]["start"] + 0.4:   # onset invadiria o bloco anterior: fica no tempo do Whisper
        s = max(w0 - 0.05, caps[-1]["start"] + 0.4)
    caps.append({"text": txt(b), "start": s, "wend": times[b[-1]][1]})
D = sum(b - a for a, b in segments(job))
for i, c in enumerate(caps):
    nxt = caps[i + 1]["start"] if i + 1 < len(caps) else D
    c["end"] = min(nxt, c["wend"] + 0.4)
    c["start"], c["end"] = shift(c["start"]), shift(c["end"])
    del c["wend"]
# bloco que ficaria menos de 0,8 s na tela pisca: junta com o seguinte (o fx_layer quebra em 2 linhas)
k = 0
while k < len(caps) - 1:
    if caps[k]["end"] - caps[k]["start"] < 0.8 and len(caps[k]["text"] + caps[k + 1]["text"]) <= 2 * MAX2 \
            and caps[k]["text"][-1] not in ".?!":
        caps[k] = {"text": caps[k]["text"] + " " + caps[k + 1]["text"], "start": caps[k]["start"], "end": caps[k + 1]["end"]}
        del caps[k + 1]
    else:
        k += 1
for i in range(len(caps) - 1):  # sem buraco curto entre blocos (evita piscar)
    if 0 < caps[i + 1]["start"] - caps[i]["end"] < 0.35:
        caps[i]["end"] = caps[i + 1]["start"]
json.dump(caps, open(OUT, "w"), ensure_ascii=False, indent=1)
for c in caps:
    print(f'{c["start"]:6.2f}-{c["end"]:6.2f}  {c["text"]}')
