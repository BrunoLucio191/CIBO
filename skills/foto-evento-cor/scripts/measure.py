"""Mede cada foto de uma pasta e gera:
  - measure.csv  (pele: ângulo/croma/L*, neutro R/G B/G, pretos/brancos/estouro)
  - faces.jpg    (folha com o recorte de pele de cada rosto, para conferir a olho)

uso: python3 measure.py PASTA SAIDA_DIR [--max 1600]
"""
import csv, glob, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
import colorlib as cl


def main():
    src, out = sys.argv[1], sys.argv[2]
    mx = int(sys.argv[sys.argv.index('--max') + 1]) if '--max' in sys.argv else 1600
    os.makedirs(out, exist_ok=True)
    files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')))
    rows, crops = [], []
    for f in files:
        x = cl.load(f, mx)
        faces = cl.detect_faces(x)
        sk, per = cl.skin_stats(x, faces)
        ne = cl.neutral_stats(x, faces)
        to = cl.tone_stats(x)
        r = {'file': os.path.basename(f), 'faces': len(per)}
        if sk:
            r.update(skin_angle=round(sk['angle'], 1), skin_dev=round(sk['angle'] - cl.SKIN_LINE, 1),
                     skin_chroma=round(sk['chroma'], 3), skin_L=round(sk['L'], 1))
        if ne:
            r.update(neutral_rg=round(ne['rg'], 3), neutral_bg=round(ne['bg'], 3))
        r.update({k: round(v, 1) for k, v in to.items()})
        rows.append(r)
        for p in per:
            bx, by, bw, bh = p['box']
            c = Image.fromarray((x[by:by + bh, bx:bx + bw] * 255).astype(np.uint8)).resize((120, 120))
            crops.append((r['file'][-9:-4], p, c))
        print(r, flush=True)
    keys = ['file', 'faces', 'skin_angle', 'skin_dev', 'skin_chroma', 'skin_L', 'neutral_rg', 'neutral_bg',
            'black', 'mid', 'white', 'clip%', 'crush%']
    with open(os.path.join(out, 'measure.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        w.writerows(rows)
    if crops:
        cols = 12
        sheet = Image.new('RGB', (cols * 124, ((len(crops) + cols - 1) // cols) * 150), (25, 25, 25))
        d = ImageDraw.Draw(sheet)
        for i, (n, p, c) in enumerate(crops):
            X, Y = (i % cols) * 124, (i // cols) * 150
            sheet.paste(c, (X + 2, Y + 2))
            d.text((X + 3, Y + 124), f"{n} {p['angle']:.0f}° L{p['L']:.0f}", fill=(255, 255, 255))
        sheet.save(os.path.join(out, 'faces.jpg'), quality=85)


if __name__ == '__main__':
    main()
