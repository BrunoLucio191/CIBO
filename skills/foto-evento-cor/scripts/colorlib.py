"""Medidas objetivas de cor para fotos: rosto/pele, neutro, pretos e brancos.

Convenções (as mesmas do vetorscópio de vídeo):
  U = 0.492 (B - Y), V = 0.877 (R - Y), sobre RGB gama sRGB 0..1, Y = BT.601.
  ângulo = atan2(V, U) em graus. Vermelho puro cai em ~103°, amarelo em ~167°,
  e a LINHA DE TOM DE PELE fica em ~123° (qualquer etnia; muda só a distância do centro).
"""
import os
os.environ.setdefault('OPENCV_LOG_LEVEL', 'ERROR')
import numpy as np
import cv2
from PIL import Image, ImageOps

SKIN_LINE = 123.0
_MODEL = os.path.join(os.path.dirname(__file__), '..', 'assets', 'face_detection_yunet_2023mar.onnx')


def load(path, max_side=None):
    im = ImageOps.exif_transpose(Image.open(path)).convert('RGB')
    if max_side:
        im.thumbnail((max_side, max_side))
    return np.asarray(im).astype(np.float32) / 255


def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def yuv(x):
    y = x @ np.array([0.299, 0.587, 0.114], np.float32)
    return y, 0.492 * (x[..., 2] - y), 0.877 * (x[..., 0] - y)


def lab(x):
    return cv2.cvtColor(np.ascontiguousarray(x, np.float32), cv2.COLOR_RGB2LAB)  # L 0..100


def detect_faces(x, score=0.7):
    """Rostos com YuNet (OpenCV, pega frontal e 3/4). Retorna caixas (x, y, w, h) na escala de x."""
    H, W = x.shape[:2]
    det = cv2.FaceDetectorYN.create(_MODEL, '', (W, H), score, 0.3, 5000)
    bgr = cv2.cvtColor((x * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
    _, res = det.detect(bgr)
    faces = []
    for r in (res if res is not None else []):
        bx, by, bw, bh = [int(round(v)) for v in r[:4]]
        bx, by = max(0, bx), max(0, by)
        bw, bh = min(bw, W - bx), min(bh, H - by)
        if bw < 20 or bh < 20:
            continue
        m = skin_mask(x, (bx, by, bw, bh))
        if m is not None and m.sum() > 80:  # descarta rosto sem pele medível
            faces.append((bx, by, bw, bh))
    return faces


def skin_mask(x, box):
    """Pixels de pele dentro do miolo do rosto: tira barba/cabelo/sombra (escuros),
    brilho especular (claros) e o que está longe do quadrante de pele no vetorscópio."""
    bx, by, bw, bh = box
    x0, x1 = bx + int(bw * 0.2), bx + int(bw * 0.8)
    y0, y1 = by + int(bh * 0.2), by + int(bh * 0.65)  # testa/bochechas, acima da barba
    roi = x[y0:y1, x0:x1]
    if roi.size == 0:
        return None
    y, u, v = yuv(roi)
    ang = np.degrees(np.arctan2(v, u))
    chroma = np.hypot(u, v)
    m = (y > 0.18) & (y < 0.92) & (chroma > 0.02) & (ang > 85) & (ang < 165)
    if m.sum() < 50:
        return None
    lo, hi = np.percentile(y[m], [15, 90])  # tira sombra e brilho dentro do rosto
    m &= (y >= lo) & (y <= hi)
    full = np.zeros(x.shape[:2], bool)
    full[y0:y1, x0:x1] = m
    return full


def skin_stats(x, faces):
    """Mediana de ângulo, croma e L* da pele de todos os rostos (ponderado por área)."""
    px = []
    per = []
    for b in faces:
        m = skin_mask(x, b)
        if m is None:
            continue
        p = x[m]
        px.append(p)
        per.append(face_numbers(p) | {'box': b})
    if not px:
        return None, per
    return face_numbers(np.concatenate(px)), per


def face_numbers(p):
    y, u, v = yuv(p[None])
    mu, mv = float(np.median(u)), float(np.median(v))
    L = float(np.median(lab(p[None])[..., 0]))
    return {'angle': float(np.degrees(np.arctan2(mv, mu))), 'chroma': float(np.hypot(mu, mv)),
            'L': L, 'n': int(p.shape[0])}


def neutral_stats(x, faces=()):
    """Pixels quase sem cor e fora de estouro/sombra (parede, piso, tripé, camisa cinza).
    Não é um neutro garantido: é o candidato. Reporta R/G e B/G da média em linear."""
    mx = x.max(-1)
    mn = x.min(-1)
    s = (mx - mn) / (mx + 1e-6)
    m = (s < 0.18) & (mx > 0.25) & (mx < 0.94)
    for (bx, by, bw, bh) in faces:
        m[by:by + bh, bx:bx + bw] = False
    if m.mean() < 0.01:
        return None
    lin = srgb_to_lin(x[m]).mean(0)
    return {'rg': float(lin[0] / lin[1]), 'bg': float(lin[2] / lin[1]), 'frac': float(m.mean())}


def tone_stats(x):
    L = lab(x)[..., 0]
    clip = float(((x > 0.985).any(-1)).mean() * 100)
    crush = float(((x < 0.01).all(-1)).mean() * 100)
    p = np.percentile(L, [0.5, 50, 99.5])
    return {'black': float(p[0]), 'mid': float(p[1]), 'white': float(p[2]), 'clip%': clip, 'crush%': crush}
