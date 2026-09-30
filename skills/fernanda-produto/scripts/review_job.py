"""Pente-fino do job ANTES do render: linguagem de edicao, motion, legenda e audio.

Uso:
  python3 review_job.py job.json --audio master16k.wav --words edit_large.json [--words2 edit_turbo.json] [--out rel.json]

--audio : audio 16 kHz mono do ARQUIVO ORIGINAL (tempos do job).
--words : transcricao com --word-timestamps do AUDIO JA EDITADO (os atrim do job), large-v3.
--words2: a mesma com o segundo modelo (turbo), para cruzar texto.
Sai com codigo 1 se houver BLOQUEIO. Avisos (AVISO) pedem olho de editor, nao travam.

Regras (vindas das correcoes do usuario e do padrao aprovado):
- todo corte cai em silencio real; jump cut sempre com troca de enquadramento; plano >= 1,2 s;
- enquadramento com intencao: nada de A/B/A/B mecanico em sequencia de planos curtos;
- referencia entra/sai no proprio corte ou longe dele (>= 1,2 s) e em pausa; nunca dois eventos visuais colados;
- zoom suave: comeca em comeco de frase, a entrada rapida nao atravessa corte, nao encosta em referencia;
- legenda: texto = fala, entrada no ataque (-0,30..+0,15 s), saida depois do ultimo fonema, <= 24 cps,
  linha <= 26 caracteres, linha nao termina em palavra funcional, termos de marca do job escritos certo;
- SFX nunca > -35 dB sobre fala > -26 dB; o fade final nao cai sobre fala.
"""
import argparse, json, os, re, subprocess, sys, unicodedata, difflib
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from timeline import load_job, segments, duration, o
from speech import edited_envelope, onset as sp_onset, offset as sp_offset

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("--audio", required=True); ap.add_argument("--words", required=True)
ap.add_argument("--words2"); ap.add_argument("--out")
a = ap.parse_args()
job = load_job(a.job)
SEGS, D = segments(job), duration(job)
ZIN = float(job.get("zoom_in", 0.6))
HOLD = float(job.get("tail_hold", 0))
out = {"BLOQUEIO": [], "AVISO": [], "OK": []}
def add(k, area, msg): out[k].append(f"[{area}] {msg}")

# ---------- audio ----------
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", a.audio, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
y = np.frombuffer(raw, np.float32); SR = 16000
def lvl(t0, t1):
    x = y[int(max(t0, 0) * SR):int(max(t1, t0 + 0.005) * SR)]
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -120.0
# audio editado (tempo do video), para pausas em tempo editado
ed = np.concatenate([y[int(s0 * SR):int(s1 * SR)] for s0, s1 in SEGS] + [np.zeros(int(HOLD * SR), np.float32)])
def lvl_e(t0, t1):
    x = ed[int(max(t0, 0) * SR):int(max(t1, t0 + 0.005) * SR)]
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -120.0
def pause_e(t, r=0.06): return lvl_e(t - r, t + r) < -40

# ---------- planos ----------
cuts_e, acc = [], 0.0
for s0, s1 in SEGS[:-1]:
    acc += s1 - s0; cuts_e.append(round(acc, 3))
shots = job.get("shots") or [[s0, s1, None] for s0, s1 in SEGS]
if job.get("shot_levels"):   # depois do face_track --apply, o 3o campo e indice de framing; o nivel fica aqui
    shots = [[s0, s1, job["shot_levels"][i]] for i, (s0, s1, _) in enumerate(shots)]
sh_e, acc = [], 0.0
for s0, s1, lv in shots:
    sh_e.append((round(acc, 3), round(acc + s1 - s0, 3), lv)); acc += s1 - s0
refs = [(round(o(job, b["start"]), 3), round(o(job, b["end"]), 3)) for b in job.get("broll", [])]
def in_ref(t, m=0.0): return any(r0 - m <= t <= r1 + m for r0, r1 in refs)
# Malu (malu_refs, tempo editado): card e tela cheia escondem o rosto dela; tela dividida nao. Plano curto ou troca sem
# mudar de nivel ali dentro nao aparece. So existe no job da Malu: nos outros jobs a revisao fica igual.
mrefs = [(r["start"], r["end"]) for r in job.get("malu_refs", []) if r["kind"] in ("card", "full")]
def in_mref(t): return any(r0 <= t <= r1 for r0, r1 in mrefs)

print(f"duracao {D:.2f} s | {len(SEGS)} trechos | {len(refs)} referencias | {len(job.get('smooth_zooms', []))} zooms")
print("\nPLANOS (tempo do video)")
for i, (t0, t1, lv) in enumerate(sh_e):
    tag = " (sob referencia)" if all(in_ref(t) or in_mref(t) for t in (t0 + 0.05, t1 - 0.05)) else ""
    print(f"  {i:2d} {t0:6.2f}-{t1:6.2f} {t1 - t0:5.2f}s  nivel {lv}{tag}")
    if t1 - t0 < 1.195 and not tag:
        add("BLOQUEIO", "plano", f"plano {i} com {t1 - t0:.2f} s ({t0:.2f}) le como flash (min 1,2 s): junte ao vizinho ou cubra com referencia")
for i in range(1, len(sh_e)):
    hidden = mrefs and (in_mref(sh_e[i][0] + 0.05) or in_mref(sh_e[i - 1][1] - 0.05))   # card/tela cheia no corte
    if sh_e[i][2] is not None and sh_e[i][2] == sh_e[i - 1][2] and not hidden:
        add("BLOQUEIO", "plano", f"jump cut em {sh_e[i][0]:.2f} sem troca de enquadramento (nivel {sh_e[i][2]} dos dois lados)")
# pingue-pongue: 4+ planos curtos seguidos alternando so entre 2 niveis
run = 1
for i in range(1, len(sh_e)):
    short = sh_e[i][1] - sh_e[i][0] < 2.6 and sh_e[i - 1][1] - sh_e[i - 1][0] < 2.6
    two = len({s[2] for s in sh_e[max(0, i - run):i + 1]}) <= 2
    run = run + 1 if (short and two) else 1
    if run == 4:
        add("AVISO", "motion", f"pingue-pongue A/B em planos curtos perto de {sh_e[i][0]:.2f}: varie o nivel com intencao (3 niveis, fechado na enfase)")

# ---------- cortes em silencio ----------
REV = [float(x) for x in job.get("cortes_revisados", [])]   # emendas ouvidas e aprovadas (tempo do original)
for (s0, s1), (n0, n1) in zip(SEGS[:-1], SEGS[1:]):
    lo, li = lvl(s1 - 0.03, s1), lvl(n0, n0 + 0.03)
    if any(abs(r - s1) < 0.02 or abs(r - n0) < 0.02 for r in REV):
        continue
    if lo > -40 or li > -40:
        add("AVISO", "corte", f"corte {s1:.2f}->{n0:.2f} (original) com som na borda (saida {lo:.0f} dB, entrada {li:.0f} dB): confirme que nao corta silaba")

# ---------- respiro nas emendas: silencio de saida + silencio de entrada ----------
def edge_sil(t0, t1, step):
    """Silencio continuo (< -40 dB) a partir de t0 andando para t1 (step +-0,01), em tempo do original."""
    k, t = 0, t0
    while (t1 - t) * step > 0 and lvl(min(t, t + step), max(t, t + step)) < -40:
        k += 1; t += step
    return k * abs(step)
GAPS = []
for (s0, s1), (n0, n1), ce in zip(SEGS[:-1], SEGS[1:], cuts_e):
    g = edge_sil(s1, s0, -0.01) + edge_sil(n0, n1, 0.01)
    GAPS.append((ce, g, s1, n0))
    if g > 0.45:
        add("BLOQUEIO", "ritmo", f"emenda em {ce:.2f} com {g:.2f} s de silencio (saida {edge_sil(s1, s0, -0.01):.2f} + entrada "
            f"{edge_sil(n0, n1, 0.01):.2f}): pausa morta, apare para ~0,25 s")

# ---------- referencias ----------
for k, (r0, r1) in enumerate(refs):
    for nome, t in (("entrada", r0), ("saida", r1)):
        dc = min([abs(t - c) for c in cuts_e] or [99])
        if 0.05 < dc < 1.2:
            add("BLOQUEIO", "referencia", f"ref {k + 1} {nome} em {t:.2f} a {dc:.2f} s de um corte: dois eventos visuais colados. Alinhe com o corte")
        if dc > 0.05 and not pause_e(t):
            add("BLOQUEIO", "referencia", f"ref {k + 1} {nome} em {t:.2f} em cima de fala ({lvl_e(t - 0.06, t + 0.06):.0f} dB): mova para a pausa")
    if r1 - r0 < 2.0:
        add("AVISO", "referencia", f"ref {k + 1} dura so {r1 - r0:.2f} s")

# ---------- zooms ----------
caps = json.load(open(job["captions"]))
for z0, z1 in job.get("smooth_zooms", []):
    before = [z0 - c for c in cuts_e if c <= z0]
    inside = [c for c in cuts_e if z0 < c < z0 + ZIN + 0.35]
    if before and min(before) < 0.5:
        add("BLOQUEIO", "motion", f"zoom em {z0:.2f} a {min(before):.2f} s depois de um corte: dois movimentos colados")
    if inside:
        add("BLOQUEIO", "motion", f"entrada do zoom em {z0:.2f} atravessa o corte em {inside[0]:.2f}")
    if any(r0 - 0.5 < z1 and z0 < r1 + 0.5 for r0, r1 in refs):
        add("BLOQUEIO", "motion", f"zoom {z0:.2f}-{z1:.2f} encosta/entra em referencia")
    if not any(abs(c["start"] - z0) <= 0.35 for c in caps):
        add("AVISO", "motion", f"zoom em {z0:.2f} nao comeca junto com uma frase/legenda")

if job.get("zoom_blur") and not job.get("zoom_shutter"):
    add("AVISO", "motion", "zoom_blur mistura quadros (tmix) e gera fantasma de mao e boca: use zoom_shutter (360) — motion blur de camera")
if job.get("smooth_zooms") and job.get("framings") and not job.get("zoom_center_face"):
    add("AVISO", "motion", "zoom ancorado no centro do quadro: com espaco de olhar o rosto escorrega no zoom (zoom_center_face)")

# ---------- legenda ----------
FUNC = {"o", "a", "os", "as", "um", "uma", "e", "de", "da", "do", "das", "dos", "na", "no", "com", "que", "sem", "em", "se",
        "por", "para", "pra", "pro", "essa", "esse", "sua", "seu", "nossa", "nosso", "eu", "você", "ela", "ele", "é", "à", "já", "mais"}
def nrm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", s)
W = [dict(w=w["word"].strip(), s=w["start"], e=w["end"]) for sg in json.load(open(a.words))["segments"] for w in sg["words"]]
W2 = [w["word"] for sg in json.load(open(a.words2))["segments"] for w in sg.get("words", [])] if a.words2 else None
from speech import align
FIRST, LAST = align(caps, [dict(word=w["w"]) for w in W])
prev_end = -1
brand = job.get("brand_terms", {})
for i, c in enumerate(caps):
    txt = c["text"].replace("\n", " "); lines = c["text"].split("\n")
    d = c["end"] - c["start"]
    cps = len(re.sub(r"\s", "", txt)) / max(d, 1e-3)
    if c["start"] < prev_end - 0.02: add("BLOQUEIO", "legenda", f"#{i} sobrepoe a anterior")
    prev_end = c["end"]
    if c["end"] > D - 0.04: add("BLOQUEIO", "legenda", f"#{i} passa do fim do video")
    if cps > 24: add("AVISO", "legenda", f"#{i} {cps:.0f} cps: '{txt}'")
    for ln in lines:
        if len(ln) > 26: add("AVISO", "legenda", f"#{i} linha com {len(ln)} caracteres: '{ln}'")
        last = nrm(ln)[-1:] or [""]
        if len(lines) > 1 and ln is not lines[-1] and last[0] in FUNC:
            add("BLOQUEIO", "legenda", f"#{i} linha termina em palavra funcional: '{ln}'")
    for errado, certo in brand.items():
        if re.search(errado, txt, re.I) and certo not in txt:
            add("BLOQUEIO", "legenda", f"#{i} marca escrita errada ('{txt}'): use '{certo}'")
    # sincronia e texto contra a fala: as MESMAS palavras que o sincronizador alinhou a este bloco
    if i not in FIRST:
        add("BLOQUEIO", "legenda", f"#{i} '{txt}' sem fala correspondente no audio editado"); continue
    ws = W[FIRST[i]:LAST[i] + 1]
    if not ws:
        add("BLOQUEIO", "legenda", f"#{i} '{txt}' sem fala correspondente no audio editado"); continue
    ratio = difflib.SequenceMatcher(None, nrm(txt), nrm(" ".join(w["w"] for w in ws))).ratio()
    if ratio < 0.8:
        add("AVISO", "legenda", f"#{i} texto x fala {ratio:.2f}: legenda '{txt}' | ouvido '{' '.join(w['w'] for w in ws)}'")
    ENV = globals().get("ENV") if globals().get("ENV") is not None else edited_envelope(a.audio, SEGS)
    globals()["ENV"] = ENV
    on = sp_onset(ENV, ws[0]["s"], ws[0]["e"])
    lead = c["start"] - (on if on is not None else ws[0]["s"])
    if any(txt.startswith(pf) for pf in job.get("caption_pins", {})):
        lead = 0.0      # bloco fixado a mao pelo editor no envelope (caso que nenhuma regra resolve)
    if lead > 0.15: add("AVISO", "legenda", f"#{i} entra {lead:.2f} s DEPOIS da fala: '{txt}'")
    if lead < -0.30: add("AVISO", "legenda", f"#{i} entra {-lead:.2f} s ANTES da fala: '{txt}'")
    # checagem independente do alinhamento: o bloco nao pode entrar antes de a fala do bloco anterior acabar
    # (com o ataque mal calibrado, "se tem o intestino preso" entrou sobre o "-da" de "intoxicada")
    # So vale quando HA pausa entre os blocos (fala continua, bloco partido no meio da frase, nao tem silencio).
    if i > 0 and (i - 1) in LAST:
        on_next = sp_onset(ENV, ws[0]["s"], ws[0]["e"])
        lim = on_next if on_next is not None else ws[0]["s"]   # a pausa tem que estar ANTES do ataque real deste bloco
        k = int(W[LAST[i - 1]]["e"] * 100)
        while k < min(len(ENV), int(lim * 100)) and not (ENV[k:k + 10] < -40).all():
            k += 1
        if k < int(lim * 100) and c["start"] < k / 100 - 0.05 and not any(txt.startswith(pf) for pf in job.get("caption_pins", {})):
            add("BLOQUEIO", "legenda", f"#{i} entra em {c['start']:.2f}, antes de a fala do bloco anterior acabar ({k / 100:.2f}): '{txt}'")
    fim_fala = sp_offset(ENV, ws[-1]["e"], caps[i + 1]["start"] if i + 1 < len(caps) else D)
    if c["end"] < fim_fala - 0.02 and (i + 1 == len(caps) or caps[i + 1]["start"] > c["end"] + 0.05):
        add("AVISO", "legenda", f"#{i} sai antes do fim da ultima palavra: '{txt}'")
kws = [k.lower() for k in job.get("keywords", [])]
for k in kws:
    if not any(k in c["text"].lower() for c in caps): add("AVISO", "legenda", f"palavra-chave '{k}' nao aparece em nenhuma legenda")

# ---------- audio: fim e SFX ----------
last_speech = max((t for t in np.arange(0, D, 0.01) if lvl_e(t, t + 0.02) > -40), default=0)
if last_speech > D - 0.35 - 0.1:
    add("BLOQUEIO", "audio", f"fala ate {last_speech:.2f} s e o fade final comeca em {D - 0.35:.2f} s: aumente tail_hold")
sfx = os.path.join(job["work"], "sfx_track.wav")
if os.path.exists(sfx):
    rs = subprocess.run(["ffmpeg", "-v", "error", "-i", sfx, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    s_ = np.frombuffer(rs, np.float32) * 10 ** (job.get("sfx_db", -6) / 20)
    n = min(len(s_), len(ed)) // 1600
    for k in range(n):
        vs = 20 * np.log10(np.sqrt(np.mean(ed[k * 1600:(k + 1) * 1600] ** 2)) + 1e-9)
        ss = 20 * np.log10(np.sqrt(np.mean(s_[k * 1600:(k + 1) * 1600] ** 2)) + 1e-9)
        if ss > -35 and vs > -26:
            add("AVISO", "audio", f"SFX {ss:.0f} dB sobre fala {vs:.0f} dB em {k * 0.1:.1f} s")
else:
    add("AVISO", "audio", "sfx_track.wav ainda nao existe: rode o prep e repita a revisao para checar SFX x fala")

print()
for k in ("BLOQUEIO", "AVISO"):
    for m in out[k]: print(f"{k:9s} {m}")
print(f"\n{len(out['BLOQUEIO'])} bloqueio(s), {len(out['AVISO'])} aviso(s)")
if a.out: json.dump(out, open(a.out, "w"), ensure_ascii=False, indent=1)
sys.exit(1 if out["BLOQUEIO"] else 0)
