"""Chamada do episódio (pilar "Episódio da semana", fundo): sobre o corte já renderizado
(legenda animada) entra o nome do convidado na tela depois da frase de impacto e, depois do
corte no auge, um card de 2,5 s "O RESTO ESTÁ NO EPISÓDIO" + "Episódio completo: Bombordo e
Boreste no YouTube" (CTA da estratégia). Uma passada de vídeo; áudio original com silêncio no card.
Aprovado no EP 04 (Ayrton Fernandes).

  python3 chamada.py VIDEO.mp4 --nome "ARTHUR NETO" --sub "Sócio da Alphamar Agência Marítima" \
      --logo .../logo_podcast.png --lt 4.0 8.0 [--card 2.5]
--lt: entrada e saída do nome na tela (s do vídeo final, que começa com 1 frame de capa)."""
import os, sys, subprocess, shutil, argparse
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT = os.path.expanduser('~/.claude/skills/bombordo-boreste/assets/CalSans-Regular.ttf')
BLUE = (79, 149, 255, 255); NAVY = (6, 10, 20)
ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--nome', required=True)
ap.add_argument('--sub', required=True); ap.add_argument('--logo', required=True)
ap.add_argument('--lt', nargs=2, type=float, required=True); ap.add_argument('--card', type=float, default=2.5)
ap.add_argument('--y', type=int, default=1060, help='topo do nome na tela (px); fique fora da faixa da legenda (cap_cy ± 210)')
A = ap.parse_args()
LT_IN, LT_OUT = A.lt; CARD = A.card; LOGO = A.logo
SP = os.environ.get('TMPDIR', '/tmp')

def lower_third(out):
    im = Image.new('RGBA', (W, 230), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 62); f2 = ImageFont.truetype(FONT, 34)
    l1, l2 = A.nome, A.sub
    w = max(d.textlength(l1, font=f1), d.textlength(l2, font=f2)) + 96
    d.rounded_rectangle([60, 20, 60 + w, 200], 22, fill=(*NAVY, 175))
    d.rounded_rectangle([60, 20, 72, 200], 6, fill=BLUE)
    top1 = f1.getbbox('H')[1]; top2 = f2.getbbox('H')[1]
    d.text((108, 52 - top1), l1, font=f1, fill=(255, 255, 255, 255))
    d.text((108, 134 - top2), l2, font=f2, fill=(205, 222, 255, 255))
    im.save(out)

def card(out):
    im = Image.new('RGB', (W, H), NAVY); d = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 104); f2 = ImageFont.truetype(FONT, 42)
    top1 = f1.getbbox('H')[1]; top2 = f2.getbbox('H')[1]
    y = 800
    d.rounded_rectangle([(W - 172) // 2, y - 70, (W + 172) // 2, y - 56], 7, fill=BLUE[:3])
    for i, l in enumerate(['O RESTO ESTÁ', 'NO EPISÓDIO']):
        x = (W - d.textlength(l, font=f1)) // 2
        d.text((x, y + i * 122 - top1), l, font=f1, fill=(255, 255, 255))
    for i, l in enumerate(['Episódio completo:', 'Bombordo e Boreste no YouTube']):
        x = (W - d.textlength(l, font=f2)) // 2
        d.text((x, y + 300 + i * 58 - top2), l, font=f2, fill=(205, 222, 255))
    lg = Image.open(LOGO).convert('RGBA'); px = lg.load()
    for yy in range(lg.height):
        for xx in range(lg.width):
            r, g, b, a = px[xx, yy]
            if a > 10 and max(r, g, b) - min(r, g, b) < 45: px[xx, yy] = (255, 255, 255, a)
    lw = 150; lg = lg.resize((lw, int(lg.height * lw / lg.width)), Image.LANCZOS)
    im.paste(lg, ((W - lw) // 2, 90), lg)
    im.save(out)

def main(src):
    lt, cd = os.path.join(SP, 'chamada_lt.png'), os.path.join(SP, 'chamada_card.png')
    lower_third(lt); card(cd)
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
                               capture_output=True, text=True).stdout)
    # slide de 70 px da esquerda com ease-out cúbico + fade (0,35 s), saída em fade (0,30 s)
    ease = f"pow(1-min(1\\,max(0\\,(t-{LT_IN})/0.35))\\,3)"
    fc = (f"[1:v]format=rgba,fade=t=in:st={LT_IN}:d=0.35:alpha=1,fade=t=out:st={LT_OUT}:d=0.30:alpha=1[lt];"
          f"[0:v][lt]overlay=x='-70*{ease}':y={A.y}:enable='between(t,{LT_IN},{LT_OUT + 0.3})',setsar=1,format=yuv420p[main];"
          f"[2:v]scale={W}:{H},setsar=1,format=yuv420p,fade=t=in:st=0:d=0.30[c];"
          f"[main][c]concat=n=2:v=1:a=0[v];"
          f"[0:a]apad=whole_dur={dur + CARD:.3f}[a]")
    tmp = src + '.chamada.mp4'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src,
                    '-loop', '1', '-t', f'{dur:.3f}', '-framerate', '30', '-i', lt,
                    '-loop', '1', '-t', f'{CARD}', '-framerate', '30', '-i', cd,
                    '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
                    '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-color_range', 'tv',
                    '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709:fullrange=off',
                    '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', tmp], check=True)
    shutil.move(tmp, src); print('chamada ok:', src)

if __name__ == '__main__':
    main(A.video)
