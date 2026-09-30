"""Auditoria de fala limpa: outra voz, hesitacoes e palavra final cortada.

Uso (python do venv ~/.venvs/audiotools):
  audit_fala.py --audio master16k.wav --words whisper.json --range IN OUT [--job job.json] [--out rel.json]

Por que por REGIAO e nao por palavra: o tempo de palavra do Whisper em arquivo longo erra 0,1-0,5 s; o "é" do
comeco de uma resposta ja veio colado na cauda da pergunta do entrevistador. Aqui a decisao e feita no audio:
  1. VAD (silero) acha onde ha voz;
  2. embeddings de locutor (SpeechBrain ECAPA) em janelas de 0,8 s a cada 0,1 s;
  3. clusterizacao das janelas: a falante principal e o cluster com mais tempo de fala no trecho;
  4. voz fora desse cluster = OUTRA VOZ (entrevistador, alguem ao fundo). Volume NAO decide: o entrevistador da
     Malu falava mais alto que ela, e a pessoa do fundo mais baixo;
  5. hesitacao = token de preenchimento, vogal arrastada (> 0,45 s) ou voz da principal sem palavra transcrita;
  6. com --job: confere se o fade final (0,35 s) nao cai sobre a ultima fala.
As palavras so rotulam as regioes. Toda ocorrencia sai em tempo do arquivo, com a pausa sugerida para o corte.
"""
import argparse, json, re, unicodedata
from pathlib import Path
import numpy as np, soundfile as sf, torch

ap = argparse.ArgumentParser()
ap.add_argument("--audio", required=True); ap.add_argument("--words", required=True)
ap.add_argument("--range", nargs=2, type=float, required=True)
ap.add_argument("--job"); ap.add_argument("--out")
ap.add_argument("--other", type=float, default=0.25, help="similaridade abaixo disso com a principal = outra voz")
ap.add_argument("--end-fade", type=float, default=0.35)
a = ap.parse_args()

y, sr = sf.read(a.audio, dtype="float32")
if y.ndim > 1: y = y.mean(1)
assert sr == 16000, "use audio mono 16 kHz"
A, B = a.range
job = json.load(open(a.job)) if a.job else None
if job:
    segs, cur = [], job["in"]
    for c0, c1 in sorted(job.get("cuts", [])): segs.append((cur, c0)); cur = c1
    segs.append((cur, job["out"]))
else:
    segs = [(A, B)]
def kept(t0, t1): return sum(max(0, min(t1, s1) - max(t0, s0)) for s0, s1 in segs) > 0.03
clip = lambda t0, t1: y[int(max(t0, 0) * sr):int(t1 * sr)]
db = lambda x: float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -120.0

d = json.load(open(a.words))
W = [dict(w=x["word"].strip(), s=x["start"], e=x["end"]) for s in d["segments"] for x in s.get("words", []) if A - 2 <= x["start"] < B + 2]
def words_in(t0, t1): return " ".join(w["w"] for w in W if w["s"] < t1 and w["e"] > t0)

# 1. VAD
from silero_vad import load_silero_vad, get_speech_timestamps
off = max(A - 2, 0)
sp = get_speech_timestamps(torch.from_numpy(clip(off, B + 2).copy()), load_silero_vad(), sampling_rate=sr,
                           min_speech_duration_ms=100, min_silence_duration_ms=60)
speech = [(off + s["start"] / sr, off + s["end"] / sr) for s in sp]
def is_speech(t): return any(s0 <= t < s1 for s0, s1 in speech)

# 2. embeddings
from speechbrain.inference.speaker import EncoderClassifier
# MPS (GPU do Mac): 0,27 s por lote de 64 janelas. No CPU este torch levou ~90 s por lote (1000x mais lento).
DEV = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
enc = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir=str(Path.home() / ".cache/ecapa"),
                                     run_opts={"device": DEV})
HOP, WIN = 0.1, 0.8
ts = [t for t in np.arange(max(A - 1, 0), B + 1, HOP) if is_speech(t + WIN / 2) and (t + WIN) * sr <= len(y)]
X = []
for i in range(0, len(ts), 64):
    batch = [clip(t, t + WIN) for t in ts[i:i + 64]]
    batch = [np.pad(x[:int(WIN * sr)], (0, max(0, int(WIN * sr) - len(x)))) for x in batch]   # arredondamento na borda
    with torch.no_grad():
        e = enc.encode_batch(torch.from_numpy(np.stack(batch)).to(DEV)).squeeze(1).cpu().numpy()
    X.append(e / np.linalg.norm(e, axis=1, keepdims=True))
X = np.concatenate(X)

# 3. clusters: principal = cluster com mais janelas
from sklearn.cluster import AgglomerativeClustering
lab = AgglomerativeClustering(n_clusters=None, metric="cosine", linkage="average", distance_threshold=0.75).fit_predict(X)
main = np.bincount(lab).argmax()
cen = X[lab == main].mean(0); cen /= np.linalg.norm(cen)
sim = X @ cen
# frame (centro da janela) -> similaridade suavizada
cent = np.array(ts) + WIN / 2
def sim_at(t): 
    k = np.abs(cent - t) <= 0.25
    return float(np.median(sim[k])) if k.any() else None

issues = []
# 4. outra voz: regioes de voz com similaridade baixa
cur = None
for t, s in zip(cent, sim):
    bad = s < a.other
    if bad and cur is None: cur = [t - HOP / 2, t + HOP / 2, [s]]
    elif bad: cur[1] = t + HOP / 2; cur[2].append(s)
    elif cur is not None:
        if cur[1] - cur[0] >= 0.2: issues.append(cur)
        cur = None
if cur is not None and cur[1] - cur[0] >= 0.2: issues.append(cur)
issues = [dict(tipo="outra_voz", s=round(r[0], 2), e=round(r[1], 2), sim=round(float(np.median(r[2])), 2),
               db=round(db(clip(r[0], r[1])), 1), texto=words_in(r[0], r[1])) for r in issues if kept(r[0], r[1])]
# borda de corte: a janela de 0,8 s atravessa a emenda e "ve" a voz do lado cortado. Refaz a medida com uma janela
# de 0,8 s inteiramente DENTRO do trecho mantido; se for a principal, a regiao so encosta no corte e sai da lista.
def emb1(t0, t1):
    with torch.no_grad():
        e = enc.encode_batch(torch.from_numpy(clip(t0, t1).copy())[None].to(DEV)).squeeze().cpu().numpy()
    return e / np.linalg.norm(e)
def inside_ok(x):
    for s0, s1 in segs:
        o0, o1 = max(s0, x["s"]), min(s1, x["e"])
        if o1 - o0 <= 0.03:
            continue
        w0, w1 = (max(s0, o1 - 0.8), o1) if o1 >= s1 - 0.05 else (o0, min(s1, o0 + 0.8))
        if w1 - w0 < 0.4 or float(emb1(w0, w1) @ cen) < a.other + 0.07:
            return False
    return True
issues = [x for x in issues if not inside_ok(x)]
# regiao quase toda silencio (janela pegou pausa + ataque da palavra) da similaridade baixa sem ser outra voz
def speech_frac(t0, t1): return sum(max(0, min(t1, s1) - max(t0, s0)) for s0, s1 in speech) / max(t1 - t0, 1e-3)
issues = [x for x in issues if speech_frac(x["s"], x["e"]) >= 0.5]

# 5. hesitacoes
FILL = re.compile(r"^(eh+|éh+|ah+n*|ahn|ãh*|hu+m+|hm+|umm+|uh+|ahm|e{2,}h*|é{2,}|a{2,}h*)$")
LONGV = re.compile(r"^(e|é|a|ã|um|hum)$")
nrm = lambda t: unicodedata.normalize("NFC", t.lower()).strip(".,!?…;:\"'")
for w in W:
    t = nrm(w["w"])
    if kept(w["s"], w["e"]) and (FILL.match(t) or (LONGV.match(t) and w["e"] - w["s"] > 0.45)):
        issues.append(dict(tipo="hesitacao" if FILL.match(t) else "revisar_vogal", s=w["s"], e=w["e"], texto=w["w"],
                           dur=round(w["e"] - w["s"], 2),
                           obs=None if FILL.match(t) else "tempo do Whisper pode incluir pausa: confirme no envelope (find_pauses env)"))
for s0, s1 in speech:
    if s1 - s0 < 0.2 or not kept(s0, s1): continue
    cov = sum(max(0, min(s1, w["e"]) - max(s0, w["s"])) for w in W)
    sm = sim_at((s0 + s1) / 2)
    if cov / (s1 - s0) < 0.25 and (sm is None or sm >= a.other):
        issues.append(dict(tipo="voz_sem_palavra", s=round(s0, 2), e=round(s1, 2), sim=sm and round(sm, 2),
                           obs="da principal sem palavra: provavel 'ééé'/respiracao; ouvir"))

# 6. fim
if job:
    fala = [(s0, s1) for s0, s1 in speech if s0 < job["out"] and s1 > job["out"] - 3]
    fim = min(max(s1 for _, s1 in fala), job["out"]) if fala else job["out"]
    folga = job["out"] - fim + job.get("tail_hold", 0)   # tail_hold congela a imagem em silencio depois do out
    cortada = any(s0 < job["out"] < s1 for s0, s1 in speech)
    if (cortada and not job.get("tail_hold")) or folga < a.end_fade + 0.15:
        issues.append(dict(tipo="fim_cortado", s=round(fim, 2), e=job["out"], texto=words_in(job["out"] - 1.2, job["out"]),
                           obs=f"folga de {folga:.2f} s ate o fim; o fade de {a.end_fade} s engole a palavra -> tail_hold"))

# pausa sugerida para cada corte (centro do silencio mais proximo antes/depois)
def pause_before(t):
    prev = [s1 for s0, s1 in speech if s1 <= t + 0.02]
    return round(max(prev), 2) if prev else None
for x in issues:
    if x["tipo"] != "fim_cortado":
        x["cortar_de"] = pause_before(x["s"]); x["cortar_ate"] = next((round(s0, 2) for s0, _ in speech if s0 >= x["e"] - 0.02), None)
issues.sort(key=lambda x: x["s"])
print(f"falante principal: cluster {main} ({np.mean(lab == main) * 100:.0f}% das janelas de voz), {len(set(lab))} clusters")
for x in issues:
    extra = " ".join(f"{k}={x[k]}" for k in ("sim", "db", "dur", "cortar_de", "cortar_ate", "obs") if x.get(k) is not None)
    print(f"{x['tipo']:16s} {x['s']:8.2f}-{x['e']:8.2f}  [{x.get('texto', '')}]  {extra}")
if a.out:
    json.dump(dict(ocorrencias=issues), open(a.out, "w"), ensure_ascii=False, indent=1,
              default=lambda o: o.item() if hasattr(o, "item") else str(o))
