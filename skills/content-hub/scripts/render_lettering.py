# -*- coding: utf-8 -*-
"""Render lower-left Content Hub insight cards as RGB + matte video."""
import math
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from easing import ease_out_cubic, ease_out_back, slide_offset

W, BAND_H, FPS = 1080, 600, 30
ORANGE = (255, 116, 0, 255)
WHITE = (255, 255, 255, 255)


def font(size, weight='ExtraBold'):
    ft = ImageFont.truetype(os.environ['COVER_FONT'], size)
    try:
        ft.set_variation_by_name(weight)
    except (AttributeError, OSError):
        pass
    return ft


def wrap_words(text, ft, max_width):
    lines = []
    current = []
    for word in text.upper().split():
        trial = ' '.join(current + [word])
        if current and ft.getlength(trial) > max_width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


def choose_layout(event):
    """Choose a readable card geometry; a job width is a minimum, never a clip box."""
    text = ' '.join(str(event['text']).upper().split())
    words = text.split()
    requested = max(50, int(event.get('size', 56)))
    min_size = int(event.get('min_size', 44))
    min_card_w = max(540, int(event.get('width', 0)))
    max_card_w = min(880, int(event.get('max_width', 880)))
    preferred_lines = 1 if len(text) <= 19 else 2
    max_lines = 2 if len(words) <= 5 else 3

    best = None
    for size in range(requested, min_size - 1, -2):
        ft = font(size)
        for card_w in range(min_card_w, max_card_w + 1, 20):
            inner_w = card_w - 84
            lines = wrap_words(text, ft, inner_w)
            widths = [float(ft.getlength(' '.join(line))) for line in lines]
            if len(lines) > max_lines or max(widths, default=0) > inner_w:
                continue
            # Prefer one/two balanced lines, then the largest type and least width.
            balance = (max(widths) - min(widths)) if len(widths) > 1 else 0
            score = (abs(len(lines) - preferred_lines), -size, card_w, balance)
            if best is None or score < best[0]:
                best = (score, size, card_w, lines, widths)
        if best and best[1] == size and best[0][0] == 0:
            break
    if best is None:
        raise ValueError(f"lettering cannot fit safely: {text!r}")
    _, size, card_w, lines, widths = best
    return text, size, card_w, lines, widths


def build_card(event):
    text, size, card_w, lines, widths = choose_layout(event)
    ft = font(size)
    label_ft = font(24, 'SemiBold')
    asc, desc = ft.getmetrics()
    line_h = max(int(size * 1.14), asc + desc + 4)
    card_h = 76 + line_h * len(lines) + 34
    card = Image.new('RGBA', (card_w + 32, card_h + 32), (0, 0, 0, 0))

    # Soft lift from the video, followed by a restrained translucent panel.
    shadow = Image.new('RGBA', card.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((18, 18, card_w + 10, card_h + 10), 20, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(13))
    card.alpha_composite(shadow)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((8, 8, card_w + 8, card_h + 8), 18,
                        fill=(8, 10, 24, 205), outline=(255, 255, 255, 28), width=2)
    d.rounded_rectangle((8, 8, 18, card_h + 8), 5, fill=ORANGE)
    d.text((42, 26), event.get('label', 'CONTENT HUB  •  INSIGHT'),
           font=label_ft, fill=(255, 255, 255, 188))

    accents = {x.casefold().strip('.,:;!?%') for x in event.get('accent', '').split()}
    y = 78
    rendered_bounds = []
    for words in lines:
        x = 42
        for word in words:
            clean = word.casefold().strip('.,:;!?%')
            fill = ORANGE if clean in accents else WHITE
            d.text((x, y), word, font=ft, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 145))
            bbox = d.textbbox((x, y), word, font=ft, stroke_width=1)
            rendered_bounds.append(bbox)
            x += ft.getlength(word + ' ')
        y += line_h
    content_box = (
        min((b[0] for b in rendered_bounds), default=0),
        min((b[1] for b in rendered_bounds), default=0),
        max((b[2] for b in rendered_bounds), default=0),
        max((b[3] for b in rendered_bounds), default=0),
    )
    safe_box = (30, 70, card_w - 24, card_h - 20)
    overflow = not (
        content_box[0] >= safe_box[0] and content_box[1] >= safe_box[1]
        and content_box[2] <= safe_box[2] and content_box[3] <= safe_box[3]
    )
    if overflow:
        raise ValueError(
            f"lettering overflow for {text!r}: content={content_box}, safe={safe_box}"
        )
    meta = {
        'text': text, 'font_size': size, 'card_width': card_w,
        'card_height': card_h, 'lines': [' '.join(line) for line in lines],
        'line_widths': [round(w, 2) for w in widths],
        'content_box': content_box, 'safe_box': safe_box, 'overflow': False,
    }
    return card, meta


def paste_scaled(canvas, tile, x, y, scale, alpha):
    if alpha <= 0.003:
        return
    w = max(1, int(round(tile.width * scale)))
    h = max(1, int(round(tile.height * scale)))
    t = tile.resize((w, h), Image.Resampling.LANCZOS) if scale != 1 else tile.copy()
    if alpha < 0.999:
        a = t.getchannel('A').point(lambda v: int(v * alpha))
        t.putalpha(a)
    canvas.alpha_composite(t, (int(round(x)), int(round(y))))


def render(clip, outbase):
    events = []
    layout_report = []
    for raw in clip.get('letterings', []):
        e = dict(raw)
        e['t'] = float(e['t'])
        e['duration'] = float(e.get('duration', 2.35))
        e['tile'], layout = build_card(e)
        side = e.get('popup_side', e.get('side', 'left'))
        popup_y = int(e.get('popup_y', e.get('y', 52)))
        layout.update({'t': e['t'], 'duration': e['duration'], 'side': side, 'popup_y': popup_y})
        layout_report.append(layout)
        events.append(e)

    with open(outbase + '_layout.json', 'w', encoding='utf-8') as fh:
        json.dump({'clip': clip.get('name'), 'events': layout_report}, fh,
                  ensure_ascii=False, indent=2)

    nfr = int(math.ceil(float(clip['total']) * FPS)) + 2
    proc = subprocess.Popen([
        'ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgba',
        '-s', f'{W}x{BAND_H}', '-r', str(FPS), '-i', '-',
        '-filter_complex', '[0:v]split[c][a];[c]format=yuv420p[cv];[a]alphaextract,format=gray[av]',
        '-map', '[cv]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', outbase + '_rgb.mp4',
        '-map', '[av]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', outbase + '_a.mp4',
    ], stdin=subprocess.PIPE)
    blank = Image.new('RGBA', (W, BAND_H), (0, 0, 0, 0))
    for i in range(nfr):
        t = i / FPS
        canvas = None
        for e in events:
            dt = t - e['t']
            if dt < 0 or dt >= e['duration']:
                continue
            if canvas is None:
                canvas = blank.copy()
            enter = min(1.0, dt / 0.24)
            leave = min(1.0, (e['duration'] - dt) / 0.24)
            alpha = min(ease_out_cubic(enter), ease_out_cubic(leave))
            scale = 0.74 + 0.26 * ease_out_back(enter)
            side = e.get('popup_side', e.get('side', 'left'))
            base_x = 52 if side == 'left' else W - e['tile'].width - 52
            base_y = int(e.get('popup_y', e.get('y', 52)))
            # default 'up' + 34px matches the original hardcoded rise; override via
            # popup_dir/popup_slide_px in the clip's lettering event when a card needs
            # to enter from a different side (see lettering-motion/references/animation-catalog.md)
            slide_dx, slide_dy = slide_offset(enter, e.get('popup_dir', 'up'), e.get('popup_slide_px', 34))
            if base_x < 0 or base_x + e['tile'].width > W:
                raise ValueError(f"lettering is outside horizontal canvas: {e['text']!r}")
            if base_y < 0 or base_y + e['tile'].height > BAND_H:
                raise ValueError(f"lettering is outside vertical canvas: {e['text']!r}")
            paste_scaled(canvas, e['tile'], base_x + slide_dx, base_y + slide_dy, scale, alpha)
        proc.stdin.write((canvas or blank).tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError('lettering encode failed')
    return nfr
