#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Passe de camera da Malu: cortes, enquadramento por plano, zoom ancorado no rosto, push-in e respiro, com motion
blur de shutter 360°, num resample so (fonte 4K -> quadro final).

Uso:
  python3 camera.py job.json            -> <work>/camera.mov (ProRes 422 HQ, tempo editado, com tail_hold)
  python3 camera.py job.json --force    -> refaz mesmo com a impressao digital igual

Por que existe: o zoom da Malu rodava dentro do grafo do ffmpeg, com a escala 4K refeita 10 vezes por janela de
zoom. O v10 do reel 01 travou assim (ffmpeg parado com 11 GB num Mac de 16 GB). Aqui cada quadro sai da fonte por
um warp so, e o render.py so recebe o camera.mov (job["camera_engine"] = "malu").

Do punch.py do Bombordo: curva Easy Ease cubic-bezier(0.33,0,0.67,1) sem overshoot, escala interpolada em log
(a velocidade parece constante), quadro em movimento = media de subquadros no intervalo inteiro do obturador
(360°), trabalho direto nos planos YUV. Da Malu: zoom ancorado no rosto (olhos na mesma altura; o rosto vai do
espaco de olhar para o centro exato no auge), enquadramento por plano do face_track.py (travado ou seguido).

Movimentos em job["camera_moves"] (tempo editado; os logs de escala se somam quando se sobrepoem):
  {"t": 0.0,  "kind": "punch",   "amount": 0.14, "in": 0.3, "until": 6.0}  entrada rapida, volta lenta ate "until"
  {"t": 16.6, "kind": "push",    "amount": 0.06, "until": 19.85}           push-in lento (ease in/out) ate "until"
  {"t": 3.43, "kind": "breathe", "amount": 0.025, "until": 5.22}           respiro de plano longo (2-3%)
Sem camera_moves, os smooth_zooms antigos viram punch (zoom_amount, zoom_in).
Subquadros: sem movimento visivel (< 0,5 px no canto por quadro) = 1 warp; senao 2 a 16 subquadros, espacados
no maximo 0,5 px (mais que isso nao muda a imagem; a entrada de 0,3 s usa os 16).
"""
import argparse, hashlib, json, math, os, subprocess, sys
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bezier import bezier, EASY_EASE

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("--force", action="store_true")
ap.add_argument("--frames", help="so estes instantes (tempo editado, separados por virgula) -> PNG em --out, para conferir")
ap.add_argument("--out", default=".")
a = ap.parse_args()
job = json.load(open(a.job))
FERN = job.get("engine_scripts_fernanda", os.path.expanduser("~/.claude/skills/fernanda-produto/scripts"))
sys.path.insert(0, FERN)
from timeline import segments, duration

W, H, FPS = 2160, 3840, 30000 / 1001
WORK = job["work"]; OUT = os.path.join(WORK, "camera.mov"); STAMP = os.path.join(WORK, "camera.json")
SHOTS = job["shots"]; D = duration(job)
EASE = bezier(*job.get("camera_ease", EASY_EASE))
ZREF = float(job.get("zoom_amount", 0.14))            # zoom em que o rosto chega ao centro exato


def moves():
    mv = job.get("camera_moves")
    if mv is None:
        zin, za = float(job.get("zoom_in", 0.3)), float(job.get("zoom_amount", 0.14))
        mv = [dict(t=t0, kind="punch", amount=za, **{"in": zin}, until=t1) for t0, t1 in job.get("smooth_zooms", [])]
    return mv


MOVES = moves()


def zlog(t):
    """log da escala do zoom no instante t (tempo editado)."""
    s = 0.0
    for m in MOVES:
        t0, t1, L = float(m["t"]), float(m["until"]), math.log1p(float(m["amount"]))
        if t < t0: continue
        if m["kind"] == "punch":
            zi = float(m.get("in", 0.3)); out = max(1.2, t1 - t0 - zi)
            if t <= t0 + zi: s += L * EASE((t - t0) / zi)
            elif t <= t0 + zi + out: s += L * (1 - EASE((t - t0 - zi) / out))
        else:                                             # push e breathe: sobe com ease ate "until";
            # depois segura ate "hold_until" (padrao: solta no "until", que deve ser um corte). Sem isso um respiro
            # que termina antes de um punch no mesmo plano zeraria no meio do plano (pulo visivel).
            s += L * EASE((t - t0) / max(1e-3, t1 - t0)) if t <= t1 else (L if t <= float(m.get("hold_until", t1)) else 0.0)
    return s


# limites dos planos em tempo editado (os planos cobrem exatamente os trechos mantidos, como no render.py)
BOUNDS, acc = [], 0.0
for s0, s1, _ in SHOTS:
    BOUNDS.append((acc, acc + (s1 - s0))); acc += s1 - s0
BOUNDS[-1] = (BOUNDS[-1][0], max(BOUNDS[-1][1], D + 1))    # tail_hold (cartao final) continua no ultimo plano
# Plano de cada QUADRO pela contagem exata que o trim do ffmpeg entrega (quadros com pts em [s0, s1) a 29,97 fps).
# Decidir pelo tempo arredondado deixava, em algumas emendas, 1 quadro do plano seguinte com o enquadramento do
# anterior: um "flash" visivel no corte (reel 01 em 21 s e 30 s).
_SF = 30000 / 1001
FRAME_SHOT = []
for k_, (s0, s1, _) in enumerate(SHOTS):
    FRAME_SHOT += [k_] * (math.ceil(s1 * _SF - 1e-6) - math.ceil(s0 * _SF - 1e-6))


def shot_of_frame(i):
    return FRAME_SHOT[i] if i < len(FRAME_SHOT) else len(SHOTS) - 1


def shot_at(t):
    for k, (b0, b1) in enumerate(BOUNDS):
        if t < b1: return k
    return len(BOUNDS) - 1


def interp(keys, t):
    """keyframes [[t, v]] do face_track (tempo do plano), linear por partes como o kf_expr do render.py."""
    if t <= keys[0][0]: return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys[:-1], keys[1:]):
        if t < t1: return v0 + (v1 - v0) * (t - t0) / max(t1 - t0, 1e-3)
    return keys[-1][1]


def transform(t, k):
    """(escala_x, x0, escala_y, y0): pixel de saida u -> fonte x0 + escala*u (bordas), no plano k."""
    fm = job["framings"][SHOTS[k][2]]
    ts = min(max(t - BOUNDS[k][0], 0.0), BOUNDS[k][1] - BOUNDS[k][0])
    if isinstance(fm, dict):
        x0, y0, fw, fh = interp(fm["kx"], ts), interp(fm["ky"], ts), fm["w"], fm["h"]
    else:
        x0, y0, fw, fh = fm
    z = math.exp(zlog(t))
    if job.get("zoom_center_face", True) and job.get("face_pos"):
        FX, EY = job["face_pos"][k]
    else:
        FX, EY = 0.5, float(job.get("anchor_y", 0.38))
    p = min(1.0, (z - 1) / ZREF) if ZREF > 0 else 0.0
    wv, hv = W / z, H / z
    lx = min(max(FX * W - (FX + (0.5 - FX) * p) * wv, 0.0), W - wv)    # rosto do espaco de olhar ao centro
    ty = min(max(H * EY * (1 - 1 / z), 0.0), H - hv)                     # olhos na mesma altura
    sx, sy = fw / W, fh / H
    return sx / z, x0 + sx * lx, sy / z, y0 + sy * ty


def mats(tf):
    """Matrizes inversas (saida -> fonte) para Y e croma 4:2:0 (croma deslocado a esquerda, centrado na vertical)."""
    ax, ex, ay_, ey = tf
    bx, by = ex + 0.5 * ax - 0.5, ey + 0.5 * ay_ - 0.5                  # centros de pixel
    my = np.float32([[ax, 0, bx], [0, ay_, by]])
    mc = np.float32([[ax, 0, bx / 2], [0, ay_, (0.5 * ay_ + by - 0.5) / 2]])
    return my, mc


def disp(t, k):
    """Deslocamento (px de saida) do canto do quadro dentro do obturador de 360°."""
    h = 0.5 / FPS
    lo, hi = max(t - h, BOUNDS[k][0]), min(t + h, BOUNDS[k][1] - 1e-4)
    if hi <= lo: return 0.0
    A, B = transform(lo, k), transform(hi, k)
    d = 0.0
    for u, v in ((0, 0), (W, H), (W, 0), (0, H)):
        d = max(d, abs((A[1] + A[0] * u) - (B[1] + B[0] * u)) / A[0], abs((A[3] + A[2] * v) - (B[3] + B[2] * v)) / A[2])
    return d


FLAGS = cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP

# ---------------------------------------------------------------- referencias e fundos (job["malu_refs"], tempo editado)
# {"kind": "split", "start", "end", "file", "ss", "push": 0.06, "slide": 0.35}      tela dividida com deslize
# {"kind": "full",  "start", "end", "file", "ss", "push": 0.05, "crop_x": 0.5}       tela cheia com push lento
# {"kind": "card",  "start", "end", "rect": [x, y, w, h] (recorte do master) | "file"/"ss",
#                   "card": [w, h, cx, cy], "radius": 70, "push": 0.05, "enter": 0.45}  card flutuante sobre ela desfocada
# {"kind": "endbg", "start", "end", "enter": 0.45}                                    fundo desfocado do cartao final
# Stock passa pelo mesmo tratamento quente/suave (grade) antes: o render.py aplica depois a cor unica em tudo.
REFS = job.get("malu_refs", [])
PANEL, SHIFT, SEAM = 1500, int(job.get("shift", 1150)), 220
GRADE = job.get("ref_grade", "eq=saturation=0.86,colortemperature=temperature=5600:mix=0.35")


class Stock:
    """Quadros de uma referencia de stock, ja no tamanho do layout (cobre e recorta), a 29,97 fps."""
    def __init__(self, r, w, h):
        cx = float(r.get("crop_x", 0.5))
        vf = (f"fps=30000/1001,scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={w}:{h}:(iw-{w})*{cx}:(ih-{h})/2,{r.get('grade', GRADE)},format=yuv420p")
        self.w, self.h, self.last = w, h, None
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(r.get("ss", 0)), "-t", f'{r["end"] - r["start"] + 1:.3f}',
                                   "-i", r["file"], "-vf", vf, "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"], stdout=subprocess.PIPE)

    def next(self):
        ys, cs = self.w * self.h, (self.w // 2) * (self.h // 2)
        buf = self.p.stdout.read(ys + 2 * cs)
        if len(buf) == ys + 2 * cs:
            a_ = np.frombuffer(buf, np.uint8)
            self.last = [a_[:ys].reshape(self.h, self.w), a_[ys:ys + cs].reshape(self.h // 2, self.w // 2),
                         a_[ys + cs:].reshape(self.h // 2, self.w // 2)]
        return self.last


def ref_at(t):
    return next((r for r in REFS if r["start"] <= t < r["end"]), None)


def warp3(planes, tf, size):
    """planos (Y, U, V) -> saida size=(w, h) pela transformacao (escala_x, x0, escala_y, y0) em px da fonte."""
    w, h = size; my, mc = mats(tf)
    return [cv2.warpAffine(planes[0], my, (w, h), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE)] + \
           [cv2.warpAffine(p, mc, (w // 2, h // 2), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE) for p in planes[1:]]


def push_tf(src_w, src_h, out_w, out_h, z):
    """Recorta o centro da fonte ampliado z (push) para out_w x out_h."""
    sx, sy = src_w / out_w / z, src_h / out_h / z
    return sx, (src_w - out_w * sx) / 2, sy, (src_h - out_h * sy) / 2


def soft_blur(pl, e):
    """Desfoque do fundo (card/cartao final): reduz, borra e amplia; mistura com o nitido por e."""
    if e <= 0.001: return pl
    out = []
    for p in pl:
        h, w = p.shape; sm = cv2.resize(p, (max(1, w // 8), max(1, h // 8)), interpolation=cv2.INTER_AREA)
        b = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 5), (w, h), interpolation=cv2.INTER_CUBIC)
        out.append(p * (1 - e) + b * e)
    out[0] = 16 + (out[0] - 16) * (1 - 0.14 * e)          # escurece de leve so a luma
    return out


_MASKS = {}


def round_mask(w, h, r):
    k = (w, h, r)
    if k not in _MASKS:
        m = np.zeros((h * 2, w * 2), np.uint8)
        cv2.rectangle(m, (r * 2, 0), (w * 2 - r * 2, h * 2), 255, -1); cv2.rectangle(m, (0, r * 2), (w * 2, h * 2 - r * 2), 255, -1)
        for cx_, cy_ in ((r * 2, r * 2), (w * 2 - r * 2, r * 2), (r * 2, h * 2 - r * 2), (w * 2 - r * 2, h * 2 - r * 2)):
            cv2.circle(m, (cx_, cy_), r * 2, 255, -1, lineType=cv2.LINE_AA)
        _MASKS[k] = cv2.resize(m, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return _MASKS[k]


def blend(dst, src, a, x0, y0):
    """Cola src (planos float) com alfa a (luma) em dst na posicao (x0, y0) de luma, recortando nas bordas."""
    H_, W_ = dst[0].shape; h, w = src[0].shape
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W_, x0 + w), min(H_, y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    aa = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    dst[0][Y0:Y1, X0:X1] = dst[0][Y0:Y1, X0:X1] * (1 - aa) + src[0][Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * aa
    ac = cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    cx0, cy0, cx1, cy1 = X0 // 2, Y0 // 2, X1 // 2, Y1 // 2
    for i in (1, 2):
        s = src[i][cy0 - y0 // 2:cy1 - y0 // 2, cx0 - x0 // 2:cx1 - x0 // 2]
        c = ac[cy0 - y0 // 2:cy1 - y0 // 2, cx0 - x0 // 2:cx1 - x0 // 2]
        hh, ww = min(s.shape[0], cy1 - cy0), min(s.shape[1], cx1 - cx0)
        dst[i][cy0:cy0 + hh, cx0:cx0 + ww] = dst[i][cy0:cy0 + hh, cx0:cx0 + ww] * (1 - c[:hh, :ww]) + s[:hh, :ww] * c[:hh, :ww]


def compose(planes, t, k, r, stock):
    """Quadro final (planos float) no instante t com a referencia r ativa."""
    E_ = EASE; u = t - r["start"]; L = r["end"] - r["start"]
    if r["kind"] == "full":
        return [x.astype(np.float32) for x in warp3(stock, push_tf(W, H, W, H, 1 + r.get("push", 0.05) * E_(u / L)), (W, H))]
    if r["kind"] == "split":
        e = E_(u / r.get("slide", 0.35)); off = int(round(-PANEL * (1 - e))); dy = SHIFT * e
        ax, ex, ay_, ey = transform(t, k)
        out = [x.astype(np.float32) for x in warp3(planes, (ax, ex, ay_, ey - ay_ * dy), (W, H))]
        pan = [x.astype(np.float32) for x in warp3(stock, push_tf(W, PANEL, W, PANEL, 1 + r.get("push", 0.06) * E_(u / L)), (W, PANEL))]
        blend(out, pan, np.ones((PANEL, W), np.float32), 0, off)
        sy = off + PANEL; h2 = SEAM // 2                     # emenda: faixa desfocada com alfa em sino (como no render.py)
        if sy - h2 > 0 and e > 0:
            band = [out[0][sy - h2:sy + h2].copy()]
            bb = cv2.GaussianBlur(band[0], (0, 0), 16)
            wgt = np.power(np.clip(1 - np.abs(np.arange(-h2, h2) + 0.5) / h2, 0, 1), 0.8)[:, None]
            out[0][sy - h2:sy + h2] = band[0] * (1 - wgt) + bb * wgt
        return out
    if r["kind"] in ("card", "endbg"):
        e = E_(u / r.get("enter", 0.45))
        out = soft_blur([x.astype(np.float32) for x in warp3(planes, transform(t, k), (W, H))], e)
        if r["kind"] == "endbg": return out
        cw, ch, ccx, ccy = r["card"]; rad = r.get("radius", 70); z = 1 + r.get("push", 0.05) * E_(u / L)
        if "rect" in r:
            x0, y0, w0, h0 = r["rect"]; sx, sy = w0 / cw / z, h0 / ch / z
            src = warp3(planes, (sx, x0 + (w0 - cw * sx) / 2, sy, y0 + (h0 - ch * sy) / 2), (cw, ch))
        else:
            src = warp3(stock, push_tf(stock[0].shape[1], stock[0].shape[0], cw, ch, z), (cw, ch))
        s = 0.94 + 0.06 * e; ww, hh = int(cw * s) // 2 * 2, int(ch * s) // 2 * 2
        card = [cv2.resize(p.astype(np.float32), (ww // (1 if i == 0 else 2), hh // (1 if i == 0 else 2)), interpolation=cv2.INTER_AREA)
                for i, p in enumerate(src)]
        m = round_mask(ww, hh, int(rad * s)) * e
        x0, y0 = int(ccx - ww / 2), int(ccy - hh / 2 + 90 * (1 - e))
        sh = cv2.GaussianBlur(np.pad(m, 60), (0, 0), 28) * 0.38            # sombra suave, deslocada para baixo
        blend(out, [np.full(sh.shape, 16, np.float32), np.full((sh.shape[0] // 2, sh.shape[1] // 2), 128, np.float32),
                    np.full((sh.shape[0] // 2, sh.shape[1] // 2), 128, np.float32)], sh, x0 - 60, y0 - 60 + 36)
        blend(out, card, m, x0, y0)
        return out
    raise SystemExit(f"camera: referencia desconhecida {r['kind']}")


def ref_disp(r, t):
    """Deslocamento por quadro (px) da animacao da referencia, para escolher os subquadros."""
    if r["kind"] == "split":
        d = r.get("slide", 0.35)
        return PANEL * abs(EASE(min(1, (t - r["start"] + 0.5 / FPS) / d)) - EASE(max(0, (t - r["start"] - 0.5 / FPS) / d)))
    if r["kind"] == "card":
        d = r.get("enter", 0.45)
        return 120 * abs(EASE(min(1, (t - r["start"] + 0.5 / FPS) / d)) - EASE(max(0, (t - r["start"] - 0.5 / FPS) / d)))
    return 0.0


def render_ref(planes, t, k, r, stock):
    d = max(ref_disp(r, t), disp(t, k) if r["kind"] != "full" else 0.0)
    n = 1 if d < 0.5 else min(16, max(2, math.ceil(2 * d)))
    lo, hi = max(BOUNDS[k][0], r["start"]), min(BOUNDS[k][1], r["end"]) - 1e-4
    acc = None
    for q in range(n):
        tq = t if n == 1 else min(max(t + ((q + 0.5) / n - 0.5) / FPS, lo), hi)
        o = compose(planes, tq, k, r, stock)
        acc = o if acc is None else [x + y for x, y in zip(acc, o)]
    return [np.clip(x / n + 0.5, 0, 255).astype(np.uint8) for x in acc], n


def render_frame(planes, t, k):
    d = disp(t, k)
    n = 1 if d < 0.5 else min(16, max(2, math.ceil(2 * d)))
    if n == 1:
        my, mc = mats(transform(t, k))
        return [cv2.warpAffine(planes[0], my, (W, H), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE)] + \
               [cv2.warpAffine(p, mc, (W // 2, H // 2), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE) for p in planes[1:]], 1
    lo, hi = BOUNDS[k]
    acc = [np.zeros((H, W), np.float32), np.zeros((H // 2, W // 2), np.float32), np.zeros((H // 2, W // 2), np.float32)]
    fp = [p.astype(np.float32) for p in planes]
    for q in range(n):
        tq = min(max(t + ((q + 0.5) / n - 0.5) / FPS, lo), hi - 1e-4)      # 360°: o intervalo inteiro do quadro
        my, mc = mats(transform(tq, k))
        acc[0] += cv2.warpAffine(fp[0], my, (W, H), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE)
        acc[1] += cv2.warpAffine(fp[1], mc, (W // 2, H // 2), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE)
        acc[2] += cv2.warpAffine(fp[2], mc, (W // 2, H // 2), flags=FLAGS, borderMode=cv2.BORDER_REPLICATE)
    return [np.clip(x / n + 0.5, 0, 255).astype(np.uint8) for x in acc], n


def fingerprint():
    keys = ("src", "rotate", "in", "out", "cuts", "shots", "framings", "face_pos", "camera_moves", "smooth_zooms",
            "zoom_amount", "zoom_in", "zoom_center_face", "anchor_y", "tail_hold", "camera_ease", "malu_refs", "shift",
            "ref_grade")
    h = hashlib.sha256(json.dumps({k: job.get(k) for k in keys}, sort_keys=True).encode())
    h.update(open(__file__, "rb").read())
    return h.hexdigest()


def one_frame(t):
    """Quadro unico no instante t (tempo editado), buscando direto na fonte e no stock (modo --frames)."""
    k = shot_at(t); s0 = SHOTS[k][0] + min(t - BOUNDS[k][0], SHOTS[k][1] - SHOTS[k][0] - 1 / FPS)
    rot = "transpose=clock," if job.get("rotate", "clock") == "clock" else ""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-display_rotation", "0", "-noautorotate", "-ss", f"{s0:.4f}", "-i", job["src"],
                          "-frames:v", "1", "-vf", f"{rot}format=yuv420p", "-f", "rawvideo", "-"], capture_output=True).stdout
    ys, cs = W * H, (W // 2) * (H // 2); a_ = np.frombuffer(raw[:ys + 2 * cs], np.uint8)
    planes = [a_[:ys].reshape(H, W), a_[ys:ys + cs].reshape(H // 2, W // 2), a_[ys + cs:].reshape(H // 2, W // 2)]
    r = ref_at(t)
    if not r: return render_frame(planes, t, k)[0]
    st = None
    if r["kind"] in ("full", "split") or (r["kind"] == "card" and "file" in r):
        size = {"full": (W, H), "split": (W, PANEL)}.get(r["kind"]) or tuple(r["card"][:2])
        st = Stock(dict(r, ss=r.get("ss", 0) + (t - r["start"])), *size).next()
    return render_ref(planes, t, k, r, st)[0]


if __name__ == "__main__" and a.frames:
    for t in [float(x) for x in a.frames.split(",")]:
        y, u, v = one_frame(t)
        yuv = np.concatenate([y.ravel(), u.ravel(), v.ravel()]).reshape(H * 3 // 2, W)
        cv2.imwrite(os.path.join(a.out, f"cam_{t:06.2f}.png"), cv2.resize(cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420), (540, 960)))
    sys.exit(0)

if __name__ == "__main__":
    fp_ = fingerprint()
    if not a.force and os.path.exists(OUT) and os.path.exists(STAMP) and json.load(open(STAMP)).get("fp") == fp_:
        print("camera.mov em dia (nada mudou no enquadramento nem nos movimentos)"); sys.exit(0)
    rot = "transpose=clock," if job.get("rotate", "clock") == "clock" else ""
    m = len(SHOTS)
    # mesma selecao de quadros do render.py (trim por plano + concat + fps + tail_hold), sem recorte nem zoom
    fc = f"[0:v]{rot}split={m}" + "".join(f"[vs{i}]" for i in range(m)) + ";"
    fc += "".join(f"[vs{i}]trim={s0}:{s1},setpts=PTS-STARTPTS[vt{i}];" for i, (s0, s1, _) in enumerate(SHOTS))
    hold = f",tpad=stop_mode=clone:stop_duration={job['tail_hold']}" if job.get("tail_hold") else ""
    fc += "".join(f"[vt{i}]" for i in range(m)) + f"concat=n={m}:v=1:a=0,fps=30000/1001{hold},format=yuv420p[v]"
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-display_rotation", "0", "-noautorotate", "-i", job["src"],
                            "-filter_complex", fc, "-map", "[v]", "-t", f"{D:.3f}", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
                           stdout=subprocess.PIPE)
    tmp = OUT + ".tmp.mov"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{W}x{H}",
                            "-r", "30000/1001", "-i", "-", "-c:v", "prores_videotoolbox", "-profile:v", "hq",
                            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", tmp],
                           stdin=subprocess.PIPE)
    ys, cs = W * H, (W // 2) * (H // 2); fsz = ys + 2 * cs
    i = nblur = 0; zmax = 0.0; cur = stock = None
    while True:
        buf = dec.stdout.read(fsz)
        if len(buf) < fsz: break
        t = i / FPS; k = shot_of_frame(i); r = ref_at(t)
        a_ = np.frombuffer(buf, np.uint8)
        planes = [a_[:ys].reshape(H, W), a_[ys:ys + cs].reshape(H // 2, W // 2), a_[ys + cs:].reshape(H // 2, W // 2)]
        if r is not cur:                                   # abre o stock da referencia que comeca
            if stock: stock.p.kill()
            stock, cur = None, r
            if r and r["kind"] in ("full", "split") or (r and r["kind"] == "card" and "file" in r):
                size = {"full": (W, H), "split": (W, PANEL)}.get(r["kind"]) or tuple(r["card"][:2])
                stock = Stock(r, *size)
        if r:
            out, n = render_ref(planes, t, k, r, stock.next() if stock else None)
        else:
            out, n = render_frame(planes, t, k)
        nblur += n > 1; zmax = max(zmax, math.expm1(zlog(t)))
        enc.stdin.write(b"".join(p.tobytes() for p in out))
        i += 1
        if i % 300 == 0: print(f"   camera: {i} quadros ({t:.1f}s)", flush=True)
    enc.stdin.close(); enc.wait(); dec.wait()
    if dec.returncode or enc.returncode or i == 0: sys.exit("camera: ffmpeg falhou")
    os.replace(tmp, OUT)
    json.dump(dict(fp=fp_, frames=i, duration=D, blur_frames=nblur, zoom_max=round(zmax, 4), moves=MOVES), open(STAMP, "w"), indent=1)
    print(f"camera.mov: {i} quadros, {nblur} com motion blur, zoom maximo {zmax * 100:.1f}% -> {OUT}")
