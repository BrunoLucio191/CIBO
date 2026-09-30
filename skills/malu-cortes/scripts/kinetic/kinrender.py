# -*- coding: utf-8 -*-
"""Etapa 3 — camada de legenda animada quadro a quadro (adaptado do kinrender.py do Bombordo).

Do Bombordo, como esta: supersampling opcional com reducao por area, composicao pre-multiplicada (blur sem halo
escuro), linha de base comum (letra posicionada pela ascendente), destaque que escala em grupo e nunca passa da
largura, saida do bloco antes da entrada do proximo.
Da Malu: quadro 4K (2160x3840) desenhado em px nativos (no celular ja vale como supersampling 2x); Montserrat Light
no texto e SemiBold no destaque (1,3x, faixa 1,2-1,4x); cores da paleta dela; altura de CADA bloco logo abaixo do
queixo mais baixo durante todo o tempo em que o bloco fica na tela (inclui o auge de zoom e push, medido no
camera.mov), com folga para o movimento de entrada e saida; a zona segura de baixo vence e o bloco e listado.
Saida sem perdas: QuickTime Animation (qtrle, RGBA 8 bits) em quadro cheio — nada de compressao na borda fina.
"""
import math, os, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import anim
from common import hex_rgb, kdir, jsave

FPS = 30000 / 1001; W, H = 2160, 3840


class Tiles:
    def __init__(self, cfg):
        self.cfg, self.cache, self.fonts = cfg, {}, {}

    def font(self, px, role="text"):
        k = (px, role)
        if k not in self.fonts:
            self.fonts[k] = ImageFont.truetype(self.cfg["font_highlight"] if role == "hl" else self.cfg["font"], px)
        return self.fonts[k]

    def get(self, text, px, fill, role="text", shadow_alpha=None, halo=None):
        key = (text, px, fill, role, shadow_alpha, halo)
        if key in self.cache: return self.cache[key]
        c = self.cfg["color"]; f = self.font(px, role); asc, desc = f.getmetrics()
        adv = f.getlength(text); pad = int(px * 0.65)
        tw, th = int(adv) + 2 * pad, asc + desc + 2 * pad
        sa = c["shadow_alpha"] if shadow_alpha is None else shadow_alpha
        sh = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad, pad + int(px * c["shadow_offset"])), text, font=f, fill=(0, 0, 0, sa))
        out = sh.filter(ImageFilter.GaussianBlur(px * c["shadow_blur"]))
        halo = c.get("halo_alpha") if halo is None else halo
        if halo:                                      # halo escuro largo: le sobre a estante clara e os frascos brancos
            ha = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
            ImageDraw.Draw(ha).text((pad, pad), text, font=f, fill=(0, 0, 0, halo))
            out = Image.alpha_composite(ha.filter(ImageFilter.GaussianBlur(px * c["halo_blur"])), out)
        tl = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(tl).text((pad, pad), text, font=f, fill=hex_rgb(fill) + (255,))
        out = Image.alpha_composite(out, tl)
        a = np.asarray(out).astype(np.float32) / 255.0
        a[..., :3] *= a[..., 3:4]                                   # pre-multiplica
        val = dict(img=a, adv=adv, pad=pad, base=pad + asc, cap=px * 0.72, px=px)
        self.cache[key] = val; return val


def layout(block, cfg, T):
    """Posicao final de cada palavra; y relativo ao centro do bloco (0). Guarda top/bottom do bloco."""
    sz = cfg["size"]; base = int(sz["base"]); maxw = sz["max_width"]; pitch = sz["line_pitch"]
    ws = block["words"]

    def wid(seq, px, role):
        f = T.font(px, role); return sum(f.getlength(w["w"]) for w in seq) + px * 0.28 * (len(seq) - 1)
    if block["kind"] == "highlight":
        unit = [w for w in ws if not w["small"]]; lead = [w for w in ws if w["small"]]
        top_px = int(base * sz["highlight_scale"]); one_min = base * sz["highlight_min_scale"]
        big = top_px
        while wid(unit, big, "hl") > maxw and big * 0.95 >= one_min: big = int(big * 0.95)
        if wid(unit, big, "hl") <= maxw or len(unit) == 1:
            while wid(unit, big, "hl") > maxw: big = int(big * 0.95)
            rows = [unit]
        else:
            k = min(range(1, len(unit)), key=lambda k: max(wid(unit[:k], top_px, "hl"), wid(unit[k:], top_px, "hl")))
            rows = [unit[:k], unit[k:]]; big = top_px
            while max(wid(r, big, "hl") for r in rows) > maxw: big = int(big * 0.95)
        lines = ([(lead, int(base * sz["lead_scale"]), "lead")] if lead else []) + [(r, big, "hl") for r in rows]
    else:
        size = base
        # bloco que junta duas linhas da mao (relampago fundido) quebra onde o editor quebrou
        hand = next((k for k in range(1, len(ws)) if (ws[k].get("blk"), ws[k].get("line")) != (ws[k - 1].get("blk"), ws[k - 1].get("line"))), None)
        while True:
            if hand and max(wid(ws[:hand], size, "text"), wid(ws[hand:], size, "text")) <= maxw:
                lines = [(ws[:hand], size, "text"), (ws[hand:], size, "text")]; break
            if not hand and wid(ws, size, "text") <= maxw: lines = [(ws, size, "text")]; break
            best = min(range(1, len(ws)), key=lambda k: max(wid(ws[:k], size, "text"), wid(ws[k:], size, "text"))) if len(ws) > 1 else None
            if best and max(wid(ws[:best], size, "text"), wid(ws[best:], size, "text")) <= maxw:
                lines = [(ws[:best], size, "text"), (ws[best:], size, "text")]; break
            size = int(size * 0.95)
    bls = [0.0]
    for i in range(1, len(lines)):
        if lines[i - 1][2] == "lead":
            bls.append(bls[-1] + lines[i][1] * 0.72 + lines[i - 1][1] * sz["highlight_lead_gap"])
        elif lines[i][2] == "hl":
            bls.append(bls[-1] + lines[i][1] * 0.95)
        else:
            bls.append(bls[-1] + lines[i][1] * pitch)
    top = bls[0] - lines[0][1] * 0.72; bot = bls[-1] + lines[-1][1] * 0.22
    shift = -(top + bot) / 2
    placed = []; block["width"] = 0.0
    for (seq, px, role), bl in zip(lines, bls):
        f = T.font(px, "hl" if role == "hl" else "text"); sp = px * 0.28
        tot = sum(f.getlength(w["w"]) for w in seq) + sp * (len(seq) - 1)
        x = W / 2 - tot / 2; block["width"] = max(block["width"], tot)
        for w in seq:
            a = f.getlength(w["w"])
            placed.append(dict(w=w, px=px, role=role, cx=x + a / 2, cy=bl + shift - px * 0.36))
            x += a + sp
    block["top"], block["bottom"] = top + shift, bot + shift
    return placed


def timeline(blocks, cfg, total):
    """Saida de cada bloco (do Bombordo): o anterior some antes de o proximo entrar no mesmo lugar."""
    T = cfg["timing"]
    for i, b in enumerate(blocks):
        b["t_in"] = b["words"][0]["s"] - T["lead"]
        last = b["words"][-1]
        natural = max(last["e"] + T["hold_after"], b["t_in"] + T["min_block"])
        if b["kind"] == "highlight": natural = max(natural, b["t_in"] + 0.65)
        nxt = blocks[i + 1]["words"][0]["s"] - T["lead"] if i + 1 < len(blocks) else None
        ex = T["exit"]
        if nxt is None:
            t_out = min(natural, total - ex)
        else:
            # o bloco anterior some ANTES de o proximo entrar, sempre (no Bombordo o piso de 100 ms da ultima
            # palavra deixava os dois na tela juntos quando a fala e muito colada)
            t_out = min(natural, nxt - ex)
            floor = min(last["s"] + 0.10, nxt - 0.07)
            if t_out < floor:
                t_out = floor; ex = max(0.07, nxt - t_out)
        b["t_out"] = t_out; b["exit_dur"] = ex


def positions(blocks, cfg, chin, layouts, total, shots=None):
    """Centro vertical de cada bloco. Regra do usuario: abaixo do queixo MAIS BAIXO enquanto o bloco esta na tela
    (inclui o auge de qualquer zoom/push); se isso invadir a zona segura de baixo, a zona segura vence e o bloco
    entra na lista de avisos."""
    P = cfg["position"]; m = cfg["motion"]; limit = H - P["safe_bottom"]
    ct, cc, cf = np.array(chin["t"]), np.array(chin["chin"]), np.array(chin["face_h"])
    report = []
    for b in blocks:
        a0, a1 = b["t_in"] - 0.1, b["t_out"] + b["exit_dur"] + 0.1
        mid = (b["t_in"] + b["t_out"]) / 2
        lay = next((L for L in layouts if L["start"] <= mid < L["end"]), None)
        cross = [L for L in layouts if (L["start"] < b["t_out"] and L["end"] > b["t_in"]) and L is not lay]
        up = anim.RISE.get(b["preset"], 0) * m["slide_px"] + m["exit_push_px"]              # sobe na entrada/saida
        grow = (max(m["highlight_zoom_from"], 1 + m["idle_scale"]) - 1) * abs(b["top"])
        down = m["slide_px"] * 1.1 + (max(m["highlight_zoom_from"], 1 + m["idle_scale"]) - 1) * abs(b["bottom"])
        r = dict(id=b["id"], texto=" ".join(w["w"] for w in b["words"]), t_in=round(b["t_in"], 2), t_out=round(b["t_out"], 2))
        if lay:
            # no layout a legenda cai sobre a parede creme (emenda da tela dividida): halo mais forte
            b["cy"] = float(lay["cy"]); b["halo"] = P.get("layout_halo_alpha"); r.update(regra=lay.get("kind", "layout"))
        else:
            sel = (ct >= a0) & (ct <= a1)
            if not sel.any(): sel = np.abs(ct - mid) == np.abs(ct - mid).min()
            chin_max = float(cc[sel].max()); fh = float(cf[sel].max())
            gap = max(P["chin_margin"], P["chin_margin_face"] * fh)
            b["cy"] = chin_max + gap + up + grow - b["top"]
            r.update(regra="queixo", queixo_max=round(chin_max), folga=round(gap))
        bottom_needed = b["cy"] + b["bottom"] + down
        if bottom_needed > limit:
            b["cy"] -= bottom_needed - limit
            r["zona_segura_venceu"] = True
            if r.get("regra") == "queixo":
                r["distancia_do_queixo"] = round(b["cy"] + b["top"] - up - grow - r["queixo_max"])
        if cross: r["aviso_layout"] = "bloco atravessa troca de layout: " + ", ".join(L.get("kind", "?") for L in cross)
        r["cy"] = round(b["cy"]); report.append(r)
    # altura estavel dentro do plano: todos os blocos do plano (regra do queixo) ficam na altura do mais exigente
    # (continua abaixo do queixo mais baixo de cada um); a legenda so muda de altura no corte
    if shots:
        shot_of = lambda t: next((k for k, (a, e) in enumerate(shots) if a <= t < e), len(shots) - 1)
        grp = {}
        for b, r in zip(blocks, report):
            if r.get("regra") == "queixo" and not r.get("zona_segura_venceu"):
                grp.setdefault(shot_of((b["t_in"] + b["t_out"]) / 2), []).append((b, r))
        for items in grp.values():
            cy = max(b["cy"] for b, _ in items)
            for b, r in items:                       # nunca abaixo da zona segura de baixo (e nunca acima do proprio minimo)
                r["cy_bloco"] = r["cy"]
                b["cy"] = max(b["cy"], min(cy, limit - b["bottom"] - m["slide_px"] * 1.1)); r["cy"] = round(b["cy"])
    return report


def blur_img(img, amount, direction):
    if amount < 0.6: return img
    if direction == "g":
        return cv2.GaussianBlur(img, (0, 0), amount * 0.5)
    L = int(amount) | 1
    k = np.zeros((L, L), np.float32)
    if direction == "v": k[:, L // 2] = 1.0 / L
    else: k[L // 2, :] = 1.0 / L
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_CONSTANT)


def paste(canvas, oy, img, cx, cy, scale, alpha, blur, bdir, mask):
    """canvas cobre as linhas [oy, oy + altura) do quadro; cx/cy em coordenadas do quadro."""
    if alpha <= 0.003: return
    h, w = img.shape[:2]
    if abs(scale - 1) > 1e-3:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    else:
        img = img.copy()
    if mask < 0.999:
        hh, ww = img.shape[:2]; edge = mask * ww; fe = max(4.0, 0.12 * ww)
        m = np.clip((edge - np.arange(ww, dtype=np.float32)) / fe + 0.5, 0, 1)
        img *= m[None, :, None]
    img = blur_img(img, blur, bdir)
    img *= alpha
    hh, ww = img.shape[:2]
    x0, y0 = int(round(cx - ww / 2)), int(round(cy - hh / 2)) - oy
    X0, Y0 = max(0, x0), max(0, y0); X1, Y1 = min(canvas.shape[1], x0 + ww), min(canvas.shape[0], y0 + hh)
    if X1 <= X0 or Y1 <= Y0: return
    src = img[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    dst = canvas[Y0:Y1, X0:X1]
    dst *= (1 - src[..., 3:4]); dst += src


def respect_layouts(blocks, layouts, cfg):
    """Nenhum bloco fica na tela durante uma troca de layout (entrada/saida de tela dividida, card, tela cheia):
    na troca a altura certa muda (queixo x layout) e o bloco ficaria em cima do rosto deslocado.
    Palavras ditas ate 0,3 s antes da troca aparecem junto com ela; mais que isso, o bloco e dividido na troca."""
    cuts = sorted({round(L["start"], 3) for L in layouts} | {round(L["end"], 3) for L in layouts})
    out = []
    for b in blocks:
        parts = [b]
        for x in cuts:
            p = parts[-1]
            before = [w for w in p["words"] if w["s"] < x]; after = [w for w in p["words"] if w["s"] >= x]
            if not before or not after: continue
            if x - before[0]["s"] <= 0.3:                # entra depois da troca (descontada a antecipacao)
                for w in before: w["s"] = round(x + cfg["timing"]["lead"] + 0.01, 3); w["e"] = max(w["e"], w["s"] + 0.05)
            else:
                parts[-1] = dict(p, words=before)
                parts.append(dict(p, words=after, id=f'{p["id"]}b'))
        out += parts
    return out, cuts


def render(blocks_json, cfg, total, chin, layouts, out_path, shots=None, graphics=(), job=None):
    T = Tiles(cfg); C = cfg["color"]; Tm = cfg["timing"]; E = anim.E(cfg)
    import graphics as gfx
    G = [gfx.Graphic(g, cfg, T, job) for g in graphics]
    blocks = [b for b in blocks_json["blocks"] if b["words"]]
    blocks, cuts = respect_layouts(blocks, layouts, cfg)
    timeline(blocks, cfg, total)
    for b in blocks:                                  # sai antes da troca de layout
        for x in cuts:
            if b["t_in"] < x < b["t_out"] + b["exit_dur"]:
                b["t_out"] = max(b["t_in"] + 0.2, x - b["exit_dur"])
    for b in blocks: b["place"] = layout(b, cfg, T)
    report = positions(blocks, cfg, chin, layouts, total, shots)
    jsave(report, os.path.join(kdir(os.path.dirname(out_path)), "positions.json"))
    nfr = int(math.ceil(total * FPS)) + 1
    tmp = out_path + ".tmp.mov"
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
                          "-r", "30000/1001", "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", tmp], stdin=subprocess.PIPE)
    frame = np.zeros((H, W, 4), np.uint8); dirty = None
    # faixa escura em degrade atras da legenda nas referencias em tela cheia (fundo claro de stock: o dourado sumia
    # sobre o bege do microscopio). Liga e desliga com a propria referencia, que entra e sai no corte.
    scrims = [L for L in layouts if L.get("kind") == "tela cheia"]
    SH = 900; yy = np.abs(np.arange(SH, dtype=np.float32) - SH / 2) / (SH / 2)
    scrim_a = (0.60 * np.clip(1 - yy, 0, 1) ** 1.3)[:, None, None]
    scrim = np.concatenate([np.zeros((SH, W, 3), np.float32), np.repeat(scrim_a, W, axis=1)], axis=2)
    for fi in range(nfr):
        t = fi / FPS
        act = [b for b in blocks if b["t_in"] <= t < b["t_out"] + b["exit_dur"]]
        gact = [g for g in G if g.active(t)]
        sact = [L for L in scrims if L["start"] <= t < L["end"]]
        if dirty: frame[dirty[0]:dirty[1]] = 0; dirty = None
        if act or gact or sact:
            y0 = max(0, int(min([b["cy"] + b["top"] for b in act] + [g.box[0] for g in gact] + [L["cy"] - SH / 2 for L in sact])) - 260)
            y1 = min(H, int(max([b["cy"] + b["bottom"] for b in act] + [g.box[1] for g in gact] + [L["cy"] + SH / 2 for L in sact])) + 260)
            canvas = np.zeros((y1 - y0, W, 4), np.float32)
            for L in sact:                                   # pre-multiplicado: preto com alfa = so escurece
                a0 = int(L["cy"] - SH / 2) - y0; s0, s1 = max(0, -a0), min(SH, canvas.shape[0] - a0)
                if s1 > s0: canvas[a0 + s0:a0 + s1] = canvas[a0 + s0:a0 + s1] * (1 - scrim[s0:s1, :, 3:4]) + scrim[s0:s1]
            for b in act:
                life = b["t_out"] - b["t_in"]
                isc = anim.idle_tf(t - b["t_in"], life, cfg)
                ex = anim.exit_tf(t - b["t_out"], cfg, b["exit_dur"]) if t >= b["t_out"] else dict(dy=0, scale=1, alpha=1, blur=0)
                bsc = isc * ex["scale"]; bcx, bcy = W / 2, b["cy"]
                for pl in b["place"]:
                    w = pl["w"]
                    u = t - ((b["words"][0]["s"] if b["kind"] == "highlight" else w["s"]) - Tm["lead"])
                    if u < 0: continue
                    en = anim.PRESETS[b["preset"]](u, cfg)
                    if pl["role"] == "hl":
                        tile = T.get(w["w"], pl["px"], C["highlight"], "hl", C["highlight_shadow_alpha"], b.get("halo")); img = tile["img"]
                    elif pl["role"] == "lead":
                        tile = T.get(w["w"], pl["px"], C["base"], "text", None, b.get("halo")); img = tile["img"]
                    else:
                        cf = Tm["color_fade"]
                        on = E((t - (w["s"] - cf / 2)) / cf) * (1 - E((t - w["e"]) / cf))
                        tb = T.get(w["w"], pl["px"], C["base"], "text", None, b.get("halo"))
                        ta = T.get(w["w"], pl["px"], C["active"], "text", None, b.get("halo"))
                        img = tb["img"] if on <= 0.01 else (ta["img"] if on >= 0.99 else tb["img"] * (1 - on) + ta["img"] * on)
                        tile = tb
                    off_x = tile["pad"] + tile["adv"] / 2 - img.shape[1] / 2
                    off_y = tile["base"] - tile["cap"] / 2 - img.shape[0] / 2
                    esc = min(en["scale"], max(1.0, 0.96 * W / max(1.0, b["width"])))
                    gsc = bsc * esc if b["kind"] == "highlight" else bsc
                    wcx = bcx + (pl["cx"] - bcx) * gsc; wcy = bcy + pl["cy"] * gsc
                    sc = bsc * (esc if b["kind"] == "highlight" else en["scale"])
                    cx = wcx - off_x * sc + en["dx"]
                    cy = wcy - off_y * sc + en["dy"] + ex["dy"]
                    blur = en["blur"] if en["blur"] > ex["blur"] else ex["blur"]
                    bdir = en["blur_dir"] if en["blur"] >= ex["blur"] else "g"
                    paste(canvas, y0, img, cx, cy, sc, en["alpha"] * ex["alpha"], blur, bdir, en["mask"])
            for g in gact: g.draw(canvas, y0, t, paste)
            a = canvas[..., 3:4]
            rgb = np.where(a > 1e-4, canvas[..., :3] / np.maximum(a, 1e-4), 0)
            frame[y0:y1] = (np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], axis=2) * 255 + 0.5).astype(np.uint8)
            dirty = (y0, y1)
        p.stdin.write(frame.tobytes())
    p.stdin.close(); p.wait()
    if p.returncode: raise SystemExit("camada de legenda: ffmpeg falhou")
    os.replace(tmp, out_path)
    return report, nfr
