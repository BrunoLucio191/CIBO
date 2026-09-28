"""Frame-by-frame kinetic caption band (RGBA), rendered at `supersample`x and
downscaled, piped to ffmpeg as a colour + alpha-matte pair (same interface as
render_caps: caps_<clip>_rgb.mp4 / caps_<clip>_a.mp4, band centred on cap_cy).
Compositing is premultiplied so blurred/transparent edges never get dark halos.
"""
import math, subprocess
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import anim
from common import hex_rgb

FPS = 30; W = 1080


class Tiles:
    def __init__(self, cfg, S):
        self.cfg, self.S, self.cache, self.fonts = cfg, S, {}, {}

    def font(self, px):
        if px not in self.fonts: self.fonts[px] = ImageFont.truetype(self.cfg['font'], px)
        return self.fonts[px]

    def get(self, text, px, fill, glow=0.0, shadow_alpha=None):
        key = (text, px, fill, round(glow, 2), shadow_alpha)
        if key in self.cache: return self.cache[key]
        c = self.cfg['color']; f = self.font(px); asc, desc = f.getmetrics()
        adv = f.getlength(text); pad = int(px * 0.65)
        tw, th = int(adv) + 2 * pad, asc + desc + 2 * pad
        sa = c['shadow_alpha'] if shadow_alpha is None else shadow_alpha
        sh = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad, pad + int(px * c['shadow_offset'])), text, font=f, fill=(0, 0, 0, sa))
        sh = sh.filter(ImageFilter.GaussianBlur(px * c['shadow_blur']))
        out = sh
        if glow > 0:
            gl = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((pad, pad), text, font=f, fill=hex_rgb(c['glow']) + (int(255 * glow),))
            out = Image.alpha_composite(out, gl.filter(ImageFilter.GaussianBlur(px * 0.22)))
            out = Image.alpha_composite(out, gl.filter(ImageFilter.GaussianBlur(px * 0.08)))
        tl = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(tl).text((pad, pad), text, font=f, fill=hex_rgb(fill) + (255,))
        out = Image.alpha_composite(out, tl)
        a = np.asarray(out).astype(np.float32) / 255.0
        a[..., :3] *= a[..., 3:4]                                   # premultiply
        val = dict(img=a, adv=adv, pad=pad, base=pad + asc, cap=px * 0.72, px=px)
        self.cache[key] = val; return val


def layout(block, cfg, T, S, BH):
    """Final positions (in the 2x band) of every word of a block."""
    base = int(cfg['size']['base'] * S); maxw = cfg['size']['max_width'] * S; pitch = cfg['size']['line_pitch']
    ws = block['words']
    if block['kind'] == 'highlight':
        # the big unit stays on ONE line down to ~1.5x base; past that it stacks in two
        # big lines ("presidente / mais novo") instead of shrinking to a normal caption.
        # It must ALWAYS fit max_width: a clamped font size let 3-word destaques run to
        # the screen edges (under the Instagram buttons)
        unit = [w for w in ws if not w['small']]; lead = [w for w in ws if w['small']]
        top_px = int(base * cfg['size']['highlight_scale']); one_min = base * 1.5
        def wid(seq, px):
            f = T.font(px); return sum(f.getlength(w['w']) for w in seq) + px * 0.28 * (len(seq) - 1)
        big = top_px
        while wid(unit, big) > maxw and big * 0.94 >= one_min: big = int(big * 0.94)
        if wid(unit, big) <= maxw or len(unit) == 1:
            while wid(unit, big) > maxw: big = int(big * 0.94)
            rows = [unit]
        else:
            k = min(range(1, len(unit)), key=lambda k: max(wid(unit[:k], top_px), wid(unit[k:], top_px)))
            rows = [unit[:k], unit[k:]]
            ws2 = sorted(wid(r, top_px) for r in rows)
            if ws2[0] / ws2[1] < 0.45 and wid(unit, base * 1.2) <= maxw:
                # lopsided stack ("24 / funcionários") reads worse than a smaller single line
                rows = [unit]
                while wid(unit, big) > maxw: big = int(big * 0.94)
            else:
                big = top_px
                while max(wid(r, big) for r in rows) > maxw: big = int(big * 0.94)
        lines = ([(lead, int(base * 0.8))] if lead else []) + [(r, big) for r in rows]
        roles = (['lead'] if lead else []) + ['big'] * len(rows)
    else:
        size = base
        while True:
            f = T.font(size); sp = size * 0.30
            wid = lambda seq: sum(f.getlength(w['w']) for w in seq) + sp * (len(seq) - 1)
            if wid(ws) <= maxw: lines = [(ws, size)]; break
            best = min(range(1, len(ws)), key=lambda k: max(wid(ws[:k]), wid(ws[k:]))) if len(ws) > 1 else None
            if best and max(wid(ws[:best]), wid(ws[best:])) <= maxw:
                lines = [(ws[:best], size), (ws[best:], size)]; break
            size = int(size * 0.94)
        roles = ['text'] * len(lines)
    bls = [0.0]
    for i in range(1, len(lines)):
        if roles[i - 1] == 'lead':
            # small word stacked on the big one: gap = big cap height + a little air,
            # not the big line's full leading (that read as two separate captions)
            bls.append(bls[-1] + lines[i][1] * 0.72 + lines[i - 1][1] * cfg['size'].get('highlight_lead_gap', 0.22))
        elif roles[i] == 'big':
            bls.append(bls[-1] + lines[i][1] * 0.92)
        else:
            bls.append(bls[-1] + lines[i][1] * pitch)
    top = bls[0] - lines[0][1] * 0.72; bot = bls[-1] + lines[-1][1] * 0.22
    shift = BH / 2 - (top + bot) / 2
    placed = []; block['width'] = 0.0
    for (seq, px), bl in zip(lines, bls):
        f = T.font(px); sp = px * 0.28
        tot = sum(f.getlength(w['w']) for w in seq) + sp * (len(seq) - 1)
        x = W * S / 2 - tot / 2; block['width'] = max(block['width'], tot)
        for w in seq:
            a = f.getlength(w['w'])
            placed.append(dict(w=w, px=px, x=x, bl=bl + shift, cx=x + a / 2, cy=bl + shift - px * 0.36))
            x += a + sp
    return placed


def timeline(blocks, cfg, total):
    """When each block leaves. The previous block must be gone before the next one
    appears in the same spot (overlapping exit+entry read as garbled text): it exits
    ending right at the next entry, and when speech is continuous the exit shortens
    (down to ~70 ms) instead of overlapping."""
    T = cfg['timing']
    for i, b in enumerate(blocks):
        b['t_in'] = b['words'][0]['s'] - T['lead']
        last = b['words'][-1]
        natural = max(last['e'] + T['hold_after'], b['t_in'] + T['min_block'])
        if b['kind'] == 'highlight': natural = max(natural, b['t_in'] + 0.65)
        nxt = blocks[i + 1]['words'][0]['s'] - T['lead'] if i + 1 < len(blocks) else None
        ex = T['exit']
        if nxt is None:
            t_out = min(natural, total - ex)
        else:
            t_out = min(natural, nxt - ex)
            floor = last['s'] + 0.10                      # the last word is on screen at least 100 ms
            if t_out < floor:
                t_out = floor
                ex = max(0.07, nxt - t_out)
        b['t_out'] = t_out; b['exit_dur'] = ex
        b['phase'] = (i * 1.7) % 6.28


def blur_img(img, amount, direction):
    if amount < 0.6: return img
    if direction == 'g':
        return cv2.GaussianBlur(img, (0, 0), amount * 0.5)
    L = int(amount) | 1
    k = np.zeros((L, L), np.float32)
    if direction == 'v': k[:, L // 2] = 1.0 / L
    else: k[L // 2, :] = 1.0 / L
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_CONSTANT)


def paste(canvas, img, cx, cy, scale, alpha, blur, bdir, mask, S):
    if alpha <= 0.003: return
    h, w = img.shape[:2]
    if abs(scale - 1) > 1e-3:
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        img = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
    else: img = img.copy()
    if mask < 0.999:
        hh, ww = img.shape[:2]; edge = mask * ww; fe = max(4.0, 0.12 * ww)
        xs = np.arange(ww, dtype=np.float32)
        m = np.clip((edge - xs) / fe + 0.5, 0, 1)
        img *= m[None, :, None]
    img = blur_img(img, blur * S, bdir)
    img *= alpha
    hh, ww = img.shape[:2]
    x0, y0 = int(round(cx - ww / 2)), int(round(cy - hh / 2))
    X0, Y0 = max(0, x0), max(0, y0); X1, Y1 = min(canvas.shape[1], x0 + ww), min(canvas.shape[0], y0 + hh)
    if X1 <= X0 or Y1 <= Y0: return
    src = img[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    dst = canvas[Y0:Y1, X0:X1]
    dst *= (1 - src[..., 3:4]); dst += src


def render(blocks_json, cfg, total, out_prefix, t0=0.0, t1=None):
    S = int(cfg['supersample']); BH = cfg['position']['band_height']
    T = Tiles(cfg, S); C = cfg['color']; Tm = cfg['timing']
    blocks = [b for b in blocks_json['blocks'] if b['words']]
    timeline(blocks, cfg, total)
    for b in blocks: b['place'] = layout(b, cfg, T, S, BH * S)
    nfr = int(math.ceil(total * FPS)) + 2
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{BH}',
                          '-r', str(FPS), '-i', '-', '-filter_complex',
                          '[0:v]split[c][a];[c]format=yuv420p[cv];[a]alphaextract,format=gray[av]',
                          '-map', '[cv]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '14', '-pix_fmt', 'yuv420p', out_prefix + '_rgb.mp4',
                          '-map', '[av]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '12', '-pix_fmt', 'yuv420p', out_prefix + '_a.mp4'],
                         stdin=subprocess.PIPE)
    blank = np.zeros((BH, W, 4), np.uint8).tobytes()
    canvas = np.zeros((BH * S, W * S, 4), np.float32)
    for fi in range(nfr):
        t = fi / FPS
        act = [b for b in blocks if b['t_in'] <= t < b['t_out'] + b['exit_dur']]
        if not act or t < t0 or (t1 is not None and t > t1):
            p.stdin.write(blank); continue
        canvas[:] = 0
        for b in act:
            life = b['t_out'] - b['t_in']
            isc, idy = anim.idle_tf(t - b['t_in'], life, b['phase'], cfg)
            ex = anim.exit_tf(t - b['t_out'], cfg, b['exit_dur']) if t >= b['t_out'] else dict(dy=0, scale=1, alpha=1, blur=0)
            bsc = isc * ex['scale']
            bcx = W * S / 2; bcy = BH * S / 2
            for pl in b['place']:
                w = pl['w']
                # a destaque pops in as ONE unit (word-by-word left "7" hanging alone at the
                # edge of "7 de setembro"); normal blocks reveal word by word with the speech
                u = t - ((b['words'][0]['s'] if b['kind'] == 'highlight' else w['s']) - Tm['lead'])
                if u < 0: continue
                en = anim.PRESETS[b['preset']](u, cfg)
                cf = Tm['color_fade']
                on = anim.ease_out_cubic((t - (w['s'] - cf / 2)) / cf) * (1 - anim.ease_out_cubic((t - w['e']) / cf))
                hl = w.get('hl')
                if hl:
                    glow = C['glow_strength'] * (0.75 + 0.25 * on)
                    tile = T.get(w['w'], pl['px'], C['base'], glow=round(glow, 1), shadow_alpha=C['highlight_shadow_alpha'])
                    img = tile['img']
                else:
                    tb = T.get(w['w'], pl['px'], C['base']); ta = T.get(w['w'], pl['px'], C['active'])
                    img = tb['img'] if on <= 0.01 else (ta['img'] if on >= 0.99 else tb['img'] * (1 - on) + ta['img'] * on)
                    tile = tb
                # tile centre -> text centre offset
                off_x = tile['pad'] + tile['adv'] / 2 - img.shape[1] / 2
                off_y = tile['base'] - tile['cap'] / 2 - img.shape[0] / 2
                # destaque scales as a GROUP around the block centre (per-word scaling made
                # "7 de setembro" collide into "7 desetembro" mid-zoom); normal words scale alone
                # the zoom-in never pushes a wide destaque past the frame edges
                esc = min(en['scale'], max(1.0, 0.96 * W * S / max(1.0, b['width'])))
                gsc = bsc * esc if b['kind'] == 'highlight' else bsc
                wcx = bcx + (pl['cx'] - bcx) * gsc; wcy = bcy + (pl['cy'] - bcy) * gsc
                sc = bsc * (esc if b['kind'] == 'highlight' else en['scale'])
                cx = wcx - off_x * sc + en['dx'] * S
                cy = wcy - off_y * sc + (en['dy'] + idy + ex['dy']) * S
                blur = en['blur'] if en['blur'] > ex['blur'] else ex['blur']
                bdir = en['blur_dir'] if en['blur'] >= ex['blur'] else 'g'
                paste(canvas, img, cx, cy, sc, en['alpha'] * ex['alpha'], blur, bdir, en['mask'], S)
        small = cv2.resize(canvas, (W, BH), interpolation=cv2.INTER_AREA)
        a = small[..., 3:4]
        rgb = np.where(a > 1e-4, small[..., :3] / np.maximum(a, 1e-4), 0)
        outf = np.concatenate([np.clip(rgb, 0, 1), np.clip(a, 0, 1)], axis=2)
        p.stdin.write((outf * 255 + 0.5).astype(np.uint8).tobytes())
    p.stdin.close(); p.wait()
    return nfr
