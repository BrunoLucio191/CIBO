# -*- coding: utf-8 -*-
"""Graficos da Malu desenhados na mesma camada sem perdas da legenda (job["graphics"], tempo editado).

Tipos: title (gancho: revelado por mascara com blur, sai com fade e blur), callout (pilulas creme com texto
azul-marinho + rotulo), number (numero grande com unidade e linha menor), endcard (cartao creme com o produto do
master e o nome). Tudo em Easy Ease, sem spring nem overshoot, com blur de movimento na entrada; cores da paleta.
"""
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import anim
from common import hex_rgb

W, H = 2160, 3840
CREME, NAVY = "#F4EEE1", "#1F2740"


def _prem(img):
    a = np.asarray(img).astype(np.float32) / 255.0; a[..., :3] *= a[..., 3:4]; return a


def _rrect(w, h, r, fill, alpha=255):
    im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], r * 2, fill=hex_rgb(fill) + (alpha,))
    return im.resize((w, h), Image.LANCZOS)


class Graphic:
    def __init__(self, g, cfg, T, job):
        self.g, self.cfg, self.T, self.job = g, cfg, T, job
        self.t, self.out = float(g["t"]), float(g["out"]); self.E = anim.E(cfg)
        getattr(self, "_init_" + g["kind"])()

    def active(self, t): return self.t <= t < self.out + 0.5

    def ease(self, t0, d, t): return self.E((t - t0) / d)

    def exit(self, t, d=0.4):
        e = self.ease(self.out - d, d, t); return 1 - e, 14 * e, -20 * e

    # ---- gancho
    def _init_title(self):
        c = self.cfg["color"]; self.items = []
        pitch = 1.18 * 150; y = self.g["cy"] - pitch * (len(self.g["lines"]) - 1) / 2
        for i, line in enumerate(self.g["lines"]):
            hl = i == len(self.g["lines"]) - 1
            tile = self.T.get(line, 150, c["highlight"] if hl else c["base"], "hl" if hl else "text")
            self.items.append((tile, y, i * 0.14)); y += pitch
        self.box = (self.g["cy"] - 330, self.g["cy"] + 330)

    def _draw_title(self, canvas, oy, t, paste):
        xa, xb, xdy = self.exit(t, 0.45)
        for tile, y, delay in self.items:
            e = self.ease(self.t + delay, 0.55, t)
            if e <= 0: continue
            img = tile["img"]; off_y = tile["base"] - tile["cap"] / 2 - img.shape[0] / 2
            blur, bdir = (16 * (1 - e), "h") if xb < 0.5 else (xb, "g")
            paste(canvas, oy, img, W / 2 - 24 * (1 - e), y - off_y + xdy, 1.0, min(e, 1) * xa, blur, bdir, e)

    # ---- linhas de produto
    def _init_callout(self):
        f = ImageFont.truetype(self.cfg["font_highlight"], 84); self.pills = []
        for p in self.g["pills"]:
            txt = " ".join(p["text"])                                   # espacamento de letras
            tw = int(f.getlength(txt)); w, h = tw + 150, 160
            im = _rrect(w, h, h // 2, CREME, 238); d = ImageDraw.Draw(im)
            asc, desc = f.getmetrics(); d.text(((w - tw) / 2, (h - asc - desc) / 2 + 4), txt, font=f, fill=hex_rgb(NAVY) + (255,))
            self.pills.append((_prem(im), float(p["t"]), w))
        gap = 36; tot = sum(w for _, _, w in self.pills) + gap * (len(self.pills) - 1); x = W / 2 - tot / 2
        self.px, self.py = [], []
        if tot <= 1520:                                     # lado a lado
            for _, _, w in self.pills: self.px.append(x + w / 2); self.py.append(0); x += w + gap
        else:                                               # nao cabe na area segura: empilha, centradas
            for k in range(len(self.pills)): self.px.append(W / 2); self.py.append(k * 190)
        self.label_dy = 200 + (self.py[-1] if self.py else 0)
        lb = self.g.get("label")
        self.label = (self.T.get(lb["text"], 104, self.cfg["color"]["base"], "text"), float(lb["t"])) if lb else None
        self.box = (self.g["cy"] - 140, self.g["cy"] + self.label_dy + 120)

    def _draw_callout(self, canvas, oy, t, paste):
        xa, xb, _ = self.exit(t, 0.3)
        for (img, t0, _), cx, dy in zip(self.pills, self.px, self.py):
            e = self.ease(t0, 0.35, t)
            if e > 0: paste(canvas, oy, img, cx, self.g["cy"] + dy + 40 * (1 - e), 0.96 + 0.04 * e, e * xa, max(12 * (1 - e), xb), "v", 1.0)
        if self.label:
            tile, t0 = self.label; e = self.ease(t0, 0.35, t)
            if e > 0:
                img = tile["img"]; oyy = tile["base"] - tile["cap"] / 2 - img.shape[0] / 2
                paste(canvas, oy, img, W / 2, self.g["cy"] + self.label_dy - oyy + 30 * (1 - e), 1.0, e * xa, max(12 * (1 - e), xb), "v", 1.0)

    # ---- numero
    def _init_number(self):
        c = self.cfg["color"]
        bp, up = int(self.g.get("big_px", 520)), int(self.g.get("unit_px", 170))   # menor no alto do quadro, longe do rosto
        self.big = self.T.get(self.g["big"], bp, c["highlight"], "hl")
        self.unit = self.T.get(self.g["unit"], up, c["base"], "text")
        self.sub = self.T.get(self.g["sub"], 90, c["base"], "text") if self.g.get("sub") else None
        self.box = (self.g["cy"] - 480, self.g["cy"] + 780)

    def _draw_number(self, canvas, oy, t, paste):
        xa, xb, xdy = self.exit(t, 0.3); e = self.ease(self.t, 0.4, t)
        bw, uw = self.big["adv"], self.unit["adv"]; x0 = W / 2 - (bw + 40 + uw) / 2
        base = self.g["cy"] + 180                                        # linha de base comum do numero e da unidade
        stack = bw + 40 + uw > 1520                                      # unidade longa ("milhoes de anos") vai embaixo
        pos = ((self.big, W / 2, base, 0.0), (self.unit, W / 2, base + 210, 0.08)) if stack else \
              ((self.big, x0 + bw / 2, base, 0.0), (self.unit, x0 + bw + 40 + uw / 2, base, 0.08))
        for tile, cx, bl, dl in pos:
            ee = self.ease(self.t + dl, 0.4, t)
            if ee <= 0: continue
            img = tile["img"]; cy = bl - (tile["base"] - img.shape[0] / 2)
            paste(canvas, oy, img, cx, cy + xdy, 1.08 - 0.08 * ee, ee * xa, max(10 * (1 - ee), xb), "g", 1.0)
        if self.sub:
            es = self.ease(float(self.g.get("sub_t", self.t)), 0.35, t)
            if es > 0:
                img = self.sub["img"]; cy = base + (400 if stack else 190) - (self.sub["base"] - img.shape[0] / 2)
                paste(canvas, oy, img, W / 2, cy + 26 * (1 - es) + xdy, 1.0, es * xa, max(10 * (1 - es), xb), "v", 1.0)

    # ---- cartao final
    def _init_endcard(self):
        g = self.g; cw, ch, cx, cy = g["card"]; x, y, w, h = g["rect"]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-display_rotation", "0", "-noautorotate", "-ss", str(g["src_t"]), "-i",
                              self.job["src"], "-frames:v", "1", "-vf", f"transpose=clock,format=rgb24,crop={w}:{h}:{x}:{y}", "-f", "rawvideo",
                              "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        prod = Image.frombytes("RGB", (w, h), raw)
        iw = cw - 2 * 80; ih = int(iw * h / w); prod = prod.resize((iw, ih), Image.LANCZOS).convert("RGBA")
        ch = 80 + ih + 300                                  # altura sai da foto + nome (fixa cortava o "Turi-Ita")
        m = _rrect(iw, ih, 44, "#FFFFFF").split()[3]; prod.putalpha(m)
        card = _rrect(cw, ch, 80, CREME, 250); card.alpha_composite(prod, (80, 80))
        f = ImageFont.truetype(self.cfg["font_highlight"], 150); tw = f.getlength(g["title"])
        asc, desc = f.getmetrics()
        ImageDraw.Draw(card).text(((cw - tw) / 2, 80 + ih + (300 - asc - desc) / 2), g["title"], font=f, fill=hex_rgb(NAVY) + (255,))
        self.card = _prem(card); self.ch = ch; self.box = (cy - ch / 2 - 120, cy + ch / 2 + 160)

    def _draw_endcard(self, canvas, oy, t, paste):
        e = self.ease(self.t, 0.5, t)
        if e > 0:
            cw, ch, cx, cy = self.g["card"]
            paste(canvas, oy, self.card, cx, cy + 60 * (1 - e), 0.96 + 0.04 * e, e, 14 * (1 - e), "v", 1.0)

    def draw(self, canvas, oy, t, paste):
        getattr(self, "_draw_" + self.g["kind"])(canvas, oy, t, paste)
