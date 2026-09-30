"""Correção objetiva + match de uma série de fotos de evento.

Para cada foto, em luz linear:
  1. Balanço de branco (ganho R e B): resolve duas equações
       - pele (mediana dos rostos) no ângulo da linha de pele (padrão 123°)  -> acerta o eixo verde/magenta
       - neutro de referência com R/G e B/G alvo                          -> acerta os dois eixos
     por busca em grade, com um termo pequeno que evita mexer à toa.
  2. Exposição pela pele: o rosto principal vai para o L* alvo (default 62); em fotos com vários
     rostos parecidos, só corrige se a mediana sair da faixa [L_lo, L_hi]. Curva de luminância com
     pivô no preto e no branco (não muda cor, não estoura).
  3. Pretos e brancos: ponto de preto se o 0,5% mais escuro está lavado; ombro suave se estoura.
  4. Saturação: croma da pele puxado para o alvo da série, com limite.

uso: python3 correct.py ENTRADA SAIDA [config.json] [--report report.json]
config (tudo opcional):
  {"skin_line": 123, "skin_tol": 6, "skin_angle": null, "neutral_rg": null, "neutral_bg": null, "face_L": 62, "L_lo": 52, "L_hi": 68,
   "skin_chroma": null, "files": {"DSC0001.JPG": {"neutral_weight": 0.3, "skip_wb": false}}}
  skin_angle/neutral_bg/skin_chroma null = mediana da série (a maioria define o alvo);
  o ângulo alvo é sempre preso na faixa skin_line ± skin_tol.
Grava report.json com os parâmetros aplicados em cada foto.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
import colorlib as cl

LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def analyse(x):
    faces = cl.detect_faces(x)
    sk, per = cl.skin_stats(x, faces)
    skin_px = np.concatenate([x[cl.skin_mask(x, b)] for b in faces]) if sk else None
    mx, mn = x.max(-1), x.min(-1)
    s = (mx - mn) / (mx + 1e-6)
    nm = (s < 0.18) & (mx > 0.25) & (mx < 0.94)
    for (bx, by, bw, bh) in faces:
        nm[by:by + bh, bx:bx + bw] = False
    neu_px = x[nm] if nm.mean() > 0.01 else None
    return faces, sk, per, skin_px, neu_px


def sub(p, n=6000):
    if p is None or len(p) <= n:
        return p
    return p[np.random.default_rng(0).choice(len(p), n, replace=False)]


def solve_wb(skin_px, neu_px, skin_t, t_rg, t_bg, w_neu, lim=0.25):
    """Ganhos lineares (gr, gb) com G=1, limitados a ±lim (correção maior que isso = problema de fonte)."""
    grid = np.arange(1 - lim, 1 + lim + 1e-6, 0.004, dtype=np.float32)
    sl = cl.srgb_to_lin(sub(skin_px)) if skin_px is not None else None
    nl = cl.srgb_to_lin(sub(neu_px)) if neu_px is not None else None
    best = (1e9, 1.0, 1.0)
    for gr in grid:
        # vetoriza em gb
        G = np.stack([np.full_like(grid, gr), np.ones_like(grid), grid], 1)  # (k,3)
        e = 100 * (np.log(gr) ** 2 + np.log(grid) ** 2)  # regularizador: não mexer sem motivo
        if sl is not None:
            px = cl.lin_to_srgb(sl[None] * G[:, None])  # (k,n,3)
            y = px @ np.array([0.299, 0.587, 0.114], np.float32)
            u = np.median(0.492 * (px[..., 2] - y), 1)
            v = np.median(0.877 * (px[..., 0] - y), 1)
            ang = np.degrees(np.arctan2(v, u))
            e = e + (np.maximum(np.abs(ang - skin_t) - 1.0, 0) / 2.5) ** 2  # zona morta de ±1°
        if nl is not None and w_neu > 0:
            m = (nl[None] * G[:, None]).mean(1)
            e = e + w_neu * (((np.log(m[:, 2] / m[:, 1]) - np.log(t_bg)) / 0.02) ** 2
                             + ((np.log(m[:, 0] / m[:, 1]) - np.log(t_rg)) / 0.02) ** 2)
        i = int(np.argmin(e))
        if e[i] < best[0]:
            best = (float(e[i]), float(gr), float(grid[i]))
    return best[1], best[2]


def lum_curve(lin, gam, black, shoulder, black2=0.0):
    """Mexe só na luminância (linear), mantém a proporção entre canais -> não muda matiz.
    black = ponto de preto antes da curva; black2 = depois (clarear com gamma levanta o preto)."""
    Y = lin @ LUM
    Yn = np.clip((Y - black) / (1 - black), 0, 1) ** gam
    if black2 > 0:
        Yn = np.clip((Yn - black2) / (1 - black2), 0, 1)
    if shoulder > 0:  # ombro suave acima de 0.7 linear
        k = 0.7
        over = np.clip(Yn - k, 0, None)
        Yn = np.where(Yn > k, k + over / (1 + over * shoulder / (1 - k)), Yn)
    return lin * (Yn / np.maximum(Y, 1e-6))[..., None]


def params_for(x, cfg, series, name):
    fc = cfg.get('files', {}).get(name, {})
    faces, sk, per, skin_px, neu_px = analyse(x)
    gr, gb = (1.0, 1.0) if fc.get('skip_wb') else solve_wb(
        skin_px, neu_px, series['skin_angle'], series['neutral_rg'], series['neutral_bg'], fc.get('neutral_weight', 1.0))
    g = np.array([gr, 1, gb], np.float32)
    g /= g @ LUM  # não muda o brilho
    lin = cl.srgb_to_lin(x) * g
    # exposição pela pele
    gam = 1.0
    if per:
        areas = [p['box'][2] * p['box'][3] for p in per]
        order = np.argsort(areas)[::-1]
        main = per[order[0]]
        single = len(per) == 1 or areas[order[0]] > 2.2 * areas[order[1]]
        tmp = cl.lin_to_srgb(lin)
        if single:
            m = cl.skin_mask(tmp, main['box'])
            Lnow = float(np.median(cl.lab(tmp[m][None])[..., 0]))
            Lt = cfg.get('face_L', 62)
        else:
            _, pp = cl.skin_stats(tmp, [p['box'] for p in per])
            Lnow = float(np.median([p['L'] for p in pp]))
            Lt = min(max(Lnow, cfg.get('L_lo', 52)), cfg.get('L_hi', 68))
        # L* -> Y relativo, e gamma que leva Ynow a Yt
        Yn, Yt = ((Lnow + 16) / 116) ** 3, ((Lt + 16) / 116) ** 3
        gam = float(np.clip(np.log(Yt) / np.log(Yn), 0.78, 1.3))  # no máx. ~±0,5 EV nos meios-tons
    # pretos e brancos
    Y = (lin @ LUM)
    p05, p995 = np.percentile(Y, [0.5, 99.5])
    # preto: 0,5% mais escuro deve ficar em L* ~3 (Y ~0.0033); acima disso a foto fica lavada
    black = float(p05 - 0.0033) if p05 > 0.0045 else 0.0
    clip = float((cl.lin_to_srgb(lin) > 0.985).any(-1).mean())
    shoulder = 0.6 if (clip > 0.01 or (gam < 1 and p995 > 0.8)) else 0.0
    Yg = np.clip((Y - black) / (1 - black), 0, 1) ** gam
    q = float(np.percentile(Yg, 0.5))
    black2 = q - 0.0033 if q > 0.0045 else 0.0
    out = cl.lin_to_srgb(lum_curve(lin, gam, black, shoulder, black2))
    # saturação pela croma da pele
    sf = 1.0
    if per:
        sk2, _ = cl.skin_stats(out, [p['box'] for p in per])
        if sk2:
            sf = float(np.clip(1 + (series['skin_chroma'] / sk2['chroma'] - 1) * 0.6, 0.88, 1.15))
    return dict(gr=gr, gb=gb, gam=gam, black=black, black2=black2, shoulder=shoulder, sf=sf, faces=len(per))


def apply(x, p):
    g = np.array([p['gr'], 1, p['gb']], np.float32)
    g /= g @ LUM
    lin = lum_curve(cl.srgb_to_lin(x) * g, p['gam'], p['black'], p['shoulder'], p.get('black2', 0.0))
    y = cl.lin_to_srgb(lin)
    if p['sf'] != 1:
        l = (y @ LUM)[..., None]
        y = np.clip(l + (y - l) * p['sf'], 0, 1)
    return y


def main():
    src, dst = sys.argv[1], sys.argv[2]
    cfg = json.load(open(sys.argv[3])) if len(sys.argv) > 3 and sys.argv[3].endswith('.json') and sys.argv[2] != '--report' else {}
    os.makedirs(dst, exist_ok=True)
    files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')))
    small = {f: cl.load(f, 1600) for f in files}
    # alvos da série = mediana (a maioria define o padrão), se não vierem no config
    nbg, nrg, chroma, angs = [], [], [], []
    for f, x in small.items():
        ne = cl.neutral_stats(x)
        if ne:
            nbg.append(ne['bg'])
            nrg.append(ne['rg'])
        sk, _ = cl.skin_stats(x, cl.detect_faces(x))
        if sk:
            chroma.append(sk['chroma'])
            angs.append(sk['angle'])
    # ângulo alvo da pele: o da maioria, mas nunca fora da faixa aceita da linha de pele
    line, tol = cfg.get('skin_line', cl.SKIN_LINE), cfg.get('skin_tol', 6)
    series = {'skin_angle': float(np.clip(cfg.get('skin_angle') or np.median(angs), line - tol, line + tol)),
              'neutral_rg': cfg.get('neutral_rg') or float(np.median(nrg)),
              'neutral_bg': cfg.get('neutral_bg') or float(np.median(nbg)),
              'skin_chroma': cfg.get('skin_chroma') or float(np.median(chroma))}
    print('alvos da série:', series, flush=True)
    report = {'series': series, 'config': cfg, 'files': {}}
    for f in files:
        name = os.path.basename(f)
        p = params_for(small[f], cfg, series, name)
        report['files'][name] = p
        im = Image.open(f)
        exif, icc = im.info.get('exif'), im.info.get('icc_profile')
        x = np.asarray(im.convert('RGB')).astype(np.float32) / 255
        y = apply(x, p)
        kw = dict(quality=95, subsampling=0)
        if exif:
            kw['exif'] = exif
        if icc:
            kw['icc_profile'] = icc
        Image.fromarray((y * 255 + 0.5).astype(np.uint8)).save(os.path.join(dst, name), **kw)
        print(name, {k: round(v, 3) if isinstance(v, float) else v for k, v in p.items()}, flush=True)
    rp = sys.argv[sys.argv.index('--report') + 1] if '--report' in sys.argv else os.path.join(dst, '..', 'cor_report.json')
    json.dump(report, open(rp, 'w'), indent=1)


if __name__ == '__main__':
    main()
