#!/usr/bin/env python3
"""Gera a capa 1080x1920 de um corte do Dr. Energia BR Cast.

Uso: make_cover.py <frame.png> <saida.png> "<linha 1>" ["<linha 2>" ...]
"""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

import os as _os
_AQUI = _os.path.dirname(_os.path.abspath(__file__))
ASSETS = _os.path.join(_os.path.dirname(_AQUI), "assets")
# RAIZ e a pasta do projeto do episodio; os assets vem da skill.
RAIZ = _os.environ.get("PROJETO", _os.getcwd())


W, H = 1080, 1920
VERDE = (154, 231, 28)        # #9AE71C - verde da logo
VERDE_ESCURO = (10, 83, 5)    # #0A5305 - contorno da legenda do cliente
CREME = (244, 255, 225)       # #F4FFE1
INICIO_GRAD = 0.60            # fracao da altura onde o degrade comeca a subir
TOPO_TITULO = 0.72            # onde ele ja precisa estar denso, atras do titulo
FONTE = _os.path.join(ASSETS, "Montserrat-Bold.ttf")
LOGO = _os.path.join(ASSETS, "logo_dr_energia.png")


def fundo(frame_path):
    """Frame do corte enquadrado em 9:16, escurecido e com viés verde."""
    im = Image.open(frame_path).convert("RGB")
    # cobre 1080x1920 preservando proporcao
    esc = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * esc), round(im.height * esc)), Image.LANCZOS)
    x = (im.width - W) // 2
    im = im.crop((x, 0, x + W, H))

    im = ImageEnhance.Color(im).enhance(0.90)
    im = ImageEnhance.Brightness(im).enhance(0.94)

    # Gradiente verde so no rodape: ele existe para dar contraste ao titulo e a
    # logo, que vivem de 62% da altura para baixo. Cobrindo a tela inteira ele
    # apagava o rosto, que e o que faz a pessoa parar de rolar o feed.
    grad = Image.new("L", (1, H))
    for y in range(H):
        t = y / H
        if t < INICIO_GRAD:
            a = 0.0                       # terco superior limpo: rosto e cenario
        elif t < TOPO_TITULO:
            u = (t - INICIO_GRAD) / (TOPO_TITULO - INICIO_GRAD)
            a = 190 * (u * u * (3 - 2 * u))   # smoothstep, sem borda visivel
        else:
            u = (t - TOPO_TITULO) / (1 - TOPO_TITULO)
            a = 190 + 45 * u              # rodape mais denso sob a logo
        grad.putpixel((0, y), int(a))
    grad = grad.resize((W, H))
    verde = Image.new("RGB", (W, H), (6, 46, 12))
    im = Image.composite(verde, im, grad)
    return im


def barras(im):
    """Faixas diagonais verdes discretas, ecoando as pás da logo."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i, (x, larg, a) in enumerate([(-300, 80, 26), (-170, 22, 44), (930, 62, 24)]):
        d.polygon([(x, H), (x + 520, 0), (x + 520 + larg, 0), (x + larg, H)],
                  fill=VERDE + (a,))
    ov = ov.filter(ImageFilter.GaussianBlur(1.2))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def cabe(fonte, linhas, limite):
    return all(fonte.getbbox(l)[2] - fonte.getbbox(l)[0] <= limite for l in linhas)


def titulo(im, linhas):
    margem = 72
    limite = W - 2 * margem
    tam = 128
    while tam > 52:
        f = ImageFont.truetype(FONTE, tam)
        if cabe(f, linhas, limite):
            break
        tam -= 2
    f = ImageFont.truetype(FONTE, tam)

    alt = int(tam * 1.16)
    total = alt * len(linhas)
    topo = int(H * 0.62) - total // 2

    d = ImageDraw.Draw(im)
    borda = max(4, tam // 22)
    for i, linha in enumerate(linhas):
        y = topo + i * alt
        d.text((W // 2, y), linha, font=f, fill=(255, 255, 255),
               anchor="ma", stroke_width=borda, stroke_fill=VERDE_ESCURO)

    # filete verde acima do titulo
    d.rectangle([W // 2 - 90, topo - 46, W // 2 + 90, topo - 36], fill=VERDE)
    return im


def logo(im):
    lg = Image.open(LOGO).convert("RGBA")
    larg = 300
    lg = lg.resize((larg, round(lg.height * larg / lg.width)), Image.LANCZOS)
    im = im.convert("RGBA")
    im.alpha_composite(lg, ((W - larg) // 2, H - lg.height - 96))
    return im.convert("RGB")


def main():
    frame, saida, *linhas = sys.argv[1:]
    linhas = [l.upper() for l in linhas]
    im = fundo(frame)
    im = barras(im)
    im = titulo(im, linhas)
    im = logo(im)
    im.save(saida)
    print(saida)


if __name__ == "__main__":
    main()
