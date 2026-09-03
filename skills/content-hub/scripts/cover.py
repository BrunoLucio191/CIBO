# -*- coding: utf-8 -*-
"""Build a Content Hub-specific cover with a centered guest and transparent logo."""
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

B = os.environ.get('WORK', '.')
SRCDIR = os.environ.get('SRCDIR', '.')
W, H = 1080, 1920
FONT = os.environ.get('COVER_FONT', os.environ['FONT'])
LOGO = os.environ.get('COVER_LOGO', os.environ.get('LOGO', ''))
ORANGE = (255, 116, 0)
DEEP_BLUE = (0, 2, 73)


def font(size, weight='ExtraBold'):
    ft = ImageFont.truetype(FONT, size)
    try:
        ft.set_variation_by_name(weight)
    except Exception:
        pass
    return ft


def source_time(c):
    """Map a final-timeline cover time back into the untrimmed horizontal clip."""
    wanted = float(c['cover_t'])
    elapsed = 0.0
    for start, end in c['keeps']:
        length = float(end) - float(start)
        if wanted <= elapsed + length:
            return float(start) + max(0.0, wanted - elapsed)
        elapsed += length
    return float(c['keeps'][-1][1]) - 1 / 30


def grab_centered(c):
    src = os.path.join(SRCDIR, c['src'])
    probe = json.loads(subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'json', src,
    ], check=True, capture_output=True, text=True).stdout)
    sw = int(probe['streams'][0]['width'])
    sh = int(probe['streams'][0]['height'])
    crop_w = round(sh * 9 / 16)
    cropx = float(c.get('cover_cropx', c.get('cropx', 0.5)))
    left = round(max(0, min(sw - crop_w, (sw - crop_w) * cropx)))
    vf = f'crop={crop_w}:{sh}:{left}:0,scale={W}:{H}:flags=lanczos'
    raw = subprocess.run([
        'ffmpeg', '-v', 'error', '-ss', f'{source_time(c):.6f}', '-i', src,
        '-vf', vf, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'
    ], check=True, capture_output=True).stdout
    return Image.frombytes('RGB', (W, H), raw[:W * H * 3])


def fit_lines(lines, max_width, start=96):
    size = start
    while size > 50:
        ft = font(size)
        if max(ft.getlength(line) for line in lines) <= max_width:
            return ft, size
        size -= 2
    return font(size), size


def gradient_scrim():
    mask = Image.new('L', (1, H), 0)
    for y in range(H):
        if y < 860:
            value = int(34 * (1 - y / 860))
        else:
            value = int(225 * min(1, ((y - 860) / 760) ** 1.22))
        mask.putpixel((0, y), max(0, min(235, value)))
    return mask.resize((W, H))


def build(c, _passa, out):
    im = grab_centered(c).convert('RGB')
    im = Image.composite(Image.new('RGB', (W, H), DEEP_BLUE), im, gradient_scrim())

    # Soft orange glow creates an ownable Content Hub signature without a box logo.
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((620, -260, 1280, 420), fill=(255, 116, 0, 72))
    glow = glow.filter(ImageFilter.GaussianBlur(105))
    im = Image.alpha_composite(im.convert('RGBA'), glow)

    # Transparent wordmark supplied by the client.
    try:
        logo = Image.open(LOGO).convert('RGBA')
        logo.thumbnail((300, 210), Image.Resampling.LANCZOS)
        alpha = logo.getchannel('A').point(lambda a: int(a * 0.92))
        logo.putalpha(alpha)
        logo_side = c.get('cover_logo_side')
        if not logo_side:
            logo_side = 'right' if float(c.get('cover_cropx', 0.5)) < 0.42 else 'left'
        logo_x = W - logo.width - 58 if logo_side == 'right' else 66
        im.alpha_composite(logo, (logo_x, 48))
    except Exception as exc:
        print('logo skip', exc)

    lines = [line.strip() for line in c['headline'].upper().split('\n') if line.strip()]
    ft, size = fit_lines(lines, 850, 92)
    line_h = int(size * 1.08)
    panel_h = 132 + line_h * len(lines) + 82
    panel_y = H - panel_h - 92

    panel = Image.new('RGBA', (W, panel_h + 48), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((54, 20, 1026, panel_h + 20), 28,
                         fill=(0, 2, 46, 190), outline=(255, 255, 255, 32), width=2)
    pd.rounded_rectangle((54, 20, 68, panel_h + 20), 7, fill=ORANGE + (255,))
    shadow = panel.filter(ImageFilter.GaussianBlur(22))
    im.alpha_composite(shadow, (0, panel_y))
    im.alpha_composite(panel, (0, panel_y))

    d = ImageDraw.Draw(im)
    label_ft = font(25, 'SemiBold')
    d.text((102, panel_y + 58), 'CORTE  /  CONTENT HUB', font=label_ft,
           fill=(255, 255, 255, 184))
    y = panel_y + 107
    for index, line in enumerate(lines):
        fill = ORANGE if index == len(lines) - 1 else (255, 255, 255)
        d.text((98, y), line, font=ft, fill=fill,
               stroke_width=1, stroke_fill=(0, 0, 24, 180))
        y += line_h
    d.rounded_rectangle((98, panel_y + panel_h - 24, 340, panel_y + panel_h - 14),
                        5, fill=ORANGE)
    im.convert('RGB').save(out, quality=96)


if __name__ == '__main__':
    plan = json.load(open(os.path.join(B, 'plan.json')))
    key = sys.argv[1]
    build(plan[key], f'{B}/A_{key}.mp4', f'{B}/capa_{key}.png')
    print('ok')
