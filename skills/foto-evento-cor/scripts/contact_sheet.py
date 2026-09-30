"""Folha de contato de uma pasta, para conferir a série inteira lado a lado.
uso: python3 contact_sheet.py PASTA saida.jpg"""
import glob, os, sys
from PIL import Image, ImageDraw, ImageOps
src, out = sys.argv[1], sys.argv[2]
files = sorted(f for f in glob.glob(os.path.join(src, '*')) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff')))
cols, W, H = 8, 300, 225
sheet = Image.new('RGB', (cols * W, ((len(files) + cols - 1) // cols) * (H + 20)), (30, 30, 30))
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    t = ImageOps.exif_transpose(Image.open(f)).convert('RGB')
    t.thumbnail((W - 6, H - 6))
    x, y = (i % cols) * W, (i // cols) * (H + 20)
    sheet.paste(t, (x + (W - t.width) // 2, y + (H - t.height) // 2))
    d.text((x + 5, y + H + 3), os.path.basename(f), fill=(255, 255, 255))
sheet.save(out, quality=85)
