"""Camada de legenda (qtrle com alfa) no estilo dos cortes Zeo: Montserrat Medium branca, sombra suave, uma linha.

Uso: python3 caps_layer.py captions.json DURACAO saida.mov
captions.json: [{"text", "start", "end"}] em tempo do video editado.
A faixa (2160x420) e posicionada pelo render em y=2022 (baseline 2322) ou y=1350 na tela dividida.
"""
import json, sys, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CAPS, DUR, OUT = sys.argv[1], float(sys.argv[2]), sys.argv[3]
W, BH, BASE = 2160, 420, 300
FPS = 30000 / 1001
f = ImageFont.truetype("/Users/bruno/Library/Fonts/Montserrat-VariableFont_wght.ttf", 122)
f.set_variation_by_name("Medium")
asc = f.getmetrics()[0]
caps = json.load(open(CAPS))


def render(t):
    im = Image.new("RGBA", (W, BH), (0, 0, 0, 0))
    x, y = (W - f.getlength(t)) / 2, BASE - asc
    sh = Image.new("RGBA", (W, BH), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((x + 3, y + 6), t, font=f, fill=(0, 0, 0, 190))
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(im).text((x, y), t, font=f, fill=(255, 255, 255, 255))
    return im.tobytes()


imgs = [render(c["text"]) for c in caps]
empty = Image.new("RGBA", (W, BH), (0, 0, 0, 0)).tobytes()
p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{BH}", "-r", "30000/1001",
                      "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", OUT], stdin=subprocess.PIPE)
for i in range(round(DUR * FPS)):
    t = (i + 0.5) / FPS
    p.stdin.write(next((imgs[k] for k, c in enumerate(caps) if c["start"] <= t < c["end"]), empty))
p.stdin.close(); p.wait()
print("legenda:", round(DUR * FPS), "quadros")
