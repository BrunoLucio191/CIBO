"""Legenda animada + lettering (estilo dinamico pedido pelo usuario: "monotono e chato" sem isso).

Uso: python3 fx_layer.py job.json DURACAO OUT_DIR
Le do job:
  captions       [{"text","start","end"}] (tempo editado)
  caption_words  JSON do Whisper com palavras em tempo editado (para o pop da palavra-chave na hora em que ela fala)
  keywords       lista de palavras destacaveis (minusculas, sem acento opcional); 1 por bloco, a primeira que aparecer
  letterings     [{"t", "top", "main", "dur"}] (tempo editado)
Gera OUT_DIR/caps.mov (faixa 2160x480, overlay em y = CAP_Y - 30) e OUT_DIR/letter.mov (faixa 2160x1000, overlay em y = 380).
Animacoes com easing.py (lettering-motion): o bloco de legenda entra inteiro com slide up curto + fade, ja com a
palavra-chave em azul forte (sem pop palavra por palavra: o usuario achou o timing estranho); o lettering entra com
fade subindo suave e sai com fade; enquanto ha lettering na tela a legenda some (nao repetir o mesmo texto).
"""
import json, os, subprocess, sys, unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.path.insert(0, os.path.dirname(__file__))
from easing import ease_out_cubic, ease_out_back, entrance

job = json.load(open(sys.argv[1]))
DUR, OUT = float(sys.argv[2]), sys.argv[3]
FPS = 30000 / 1001
FONT = "/Users/bruno/Library/Fonts/Montserrat-VariableFont_wght.ttf"
ACCENT = (10, 52, 170, 255)   # azul forte escuro (usuario: "azul forte" e depois "deveria ser mais escuro")
WHITE = (255, 255, 255, 255)
W = 2160
CB_H, CB_BASE = 480, 330          # faixa da legenda e baseline dentro dela
LB_H = 1000                       # faixa do lettering


def font(size, weight, path=None):
    """weight: nome da variacao ("Medium") ou lista de eixos ([14, 400] no DM Sans: opsz, wght)."""
    f = ImageFont.truetype(path or FONT, size)
    if isinstance(weight, list):
        f.set_variation_by_axes(weight)
    elif weight:
        f.set_variation_by_name(weight)
    return f


# fonte opcional por job (padrao = Montserrat Medium + Bold na etiqueta azul, o estilo aprovado da Fernanda)
# key_style "plain": palavra-chave sem etiqueta, na key_font (p.ex. Playfair italico branco), mais suave e elegante
CAP_FONT, CAP_W = job.get("caption_font"), job.get("caption_weight", "Medium")
KEY_FONT, KEY_W = job.get("key_font"), job.get("key_weight", "Bold")
KEY_STYLE = job.get("key_style", "pill")
KEY_SIZE = job.get("key_scale", 1.0)


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip(".,!?:;\"'")


# ---------- legenda ----------
CAP_SIZE, KEY_SCALE = 112, 1.0
LINE_H = 138                      # entrelinha da legenda em 2 linhas
fcap = font(CAP_SIZE, CAP_W, CAP_FONT)          # usuario: "montserrat mais fino em tudo"
fkey = font(int(CAP_SIZE * KEY_SIZE), KEY_W, KEY_FONT)   # ... "e a bold pra palavras chave"
KEYS = [norm(k) for k in job.get("keywords", [])]
WORDS = []
if job.get("caption_words"):
    d = json.load(open(job["caption_words"]))
    WORDS = [(norm(w["word"]), w["start"]) for s in d["segments"] for w in s["words"]]


CAP_GLOW = float(job.get("caption_glow", 0))   # 0 = so sombra (padrao); ~0,4 = halo escuro suave p/ ler sobre frasco branco


def text_tile(t, f, fill, glow=False, outline=0, glow_alpha=0.62):
    """Palavra com sombra suave; origem fixa para a baseline ser conhecida.
    glow=True (lettering): halo escuro largo para ler sobre a prateleira cheia de frascos."""
    asc, desc = f.getmetrics()
    pad = 90 if glow else 40
    w = int(f.getlength(t)) + pad * 2
    h = asc + desc + pad * 2
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((pad + 3, pad + 7), t, font=f, fill=(0, 0, 0, 200))
    sh = sh.filter(ImageFilter.GaussianBlur(9))
    if glow:
        g = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text((pad, pad), t, font=f, fill=(0, 0, 0, 255), stroke_width=int(f.size * 0.16), stroke_fill=(0, 0, 0, 255))
        g = g.filter(ImageFilter.GaussianBlur(f.size * 0.22))
        g.putalpha(g.getchannel("A").point(lambda v: int(v * glow_alpha)))
        g.alpha_composite(sh); sh = g
    tl = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if outline:  # azul escuro sobre blusa escura: contorno branco para continuar legivel
        ImageDraw.Draw(tl).text((pad, pad), t, font=f, fill=fill, stroke_width=outline, stroke_fill=(255, 255, 255, 255))
    else:
        ImageDraw.Draw(tl).text((pad, pad), t, font=f, fill=fill, stroke_width=2, stroke_fill=(0, 0, 0, 90))
    sh.alpha_composite(tl)
    return sh, pad, asc


def pill_tile(t, f, fill=None):
    """Palavra-chave: Bold azul escuro sobre etiqueta branca arredondada (legivel sobre roupa escura e prateleira)."""
    fill = fill or ACCENT
    asc, desc = f.getmetrics()
    bb = f.getbbox(t)                     # caixa real das letras, relativa a origem do texto
    px, py = int(f.size * 0.22), int(f.size * 0.12)
    pad = 60
    w = int(f.getlength(t)) + 2 * px + 2 * pad
    h = asc + desc + 2 * pad
    ox, oy = pad + px, pad
    box = (pad, oy + bb[1] - py, pad + 2 * px + int(f.getlength(t)), oy + bb[3] + py)
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((box[0] + 2, box[1] + 8, box[2] + 2, box[3] + 8), radius=int(f.size * 0.28), fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle(box, radius=int(f.size * 0.28), fill=(255, 255, 255, 248))
    d.text((ox, oy), t, font=f, fill=fill)
    return sh, pad, asc              # colado em x - pad: a etiqueta comeca no x do slot, o texto px depois


blocks = []
for c in json.load(open(job["captions"])):
    # "\n" no texto = quebra de linha manual (por sentido); sem ela, as 2 linhas sao equilibradas pela largura
    manual = c["text"].split("\n")
    c = dict(c, text=" ".join(x.strip() for x in manual))
    words = c["text"].split()
    ki = next((i for i, w in enumerate(words) if norm(w) in KEYS), None)
    kt = c["start"]
    if ki is not None:
        cand = [t for n, t in WORDS if n == norm(words[ki]) and c["start"] - 0.15 <= t <= c["end"]]
        kt = cand[0] if cand else c["start"]
    tiles = []
    for i, w in enumerate(words):
        cg = dict(glow=True, glow_alpha=CAP_GLOW) if CAP_GLOW else {}
        tiles.append({"white": text_tile(w, fcap, WHITE, **cg),
                      "accent": (text_tile(w, fkey, WHITE, **cg) if KEY_STYLE == "plain" else pill_tile(w, fkey)) if i == ki else None,
                      "adv": (fkey.getlength(w) + (0 if KEY_STYLE == "plain" else 2 * int(fkey.size * 0.22))) if i == ki else fcap.getlength(w)})
    space = fcap.getlength(" ")
    # ate 2 linhas equilibradas (bloco por oracao, ate ~44 caracteres)
    lines = [list(range(len(tiles)))]
    if len(manual) == 2:
        k = len(manual[0].split())
        lines = [list(range(k)), list(range(k, len(tiles)))]
    elif len(c["text"]) > 26 and len(tiles) > 1:
        widths = [t["adv"] for t in tiles]
        best = min(range(1, len(tiles)), key=lambda k: abs(sum(widths[:k]) - sum(widths[k:])))
        lines = [list(range(best)), list(range(best, len(tiles)))]
    for li, ln in enumerate(lines):
        total = sum(tiles[i]["adv"] for i in ln) + space * (len(ln) - 1)
        x = (W - total) / 2
        for i in ln:
            tiles[i]["x"] = x
            tiles[i]["base"] = CB_BASE - LINE_H * (len(lines) - 1 - li)
            x += tiles[i]["adv"] + space
    blocks.append({"start": c["start"], "end": c["end"], "tiles": tiles, "ki": ki, "kt": kt, "text": c["text"]})


def paste(canvas, tile, x, y, alpha=1.0, scale=1.0):
    img, pad, asc = tile
    if scale != 1.0:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda v: int(v * alpha)))
    canvas.alpha_composite(img, (int(round(x)), int(round(y))))


def caps_frame(t):
    # enquanto um lettering esta na tela a legenda some (usuario: texto do topo nao repete na legenda)
    bi = next((i for i, b in enumerate(blocks) if b["start"] <= t < b["end"]), None)
    if bi is None or bi in HIDE or any(e["t"] <= t < e["t"] + e["dur"] for e in LET):
        return None
    b = blocks[bi]
    cv = Image.new("RGBA", (W, CB_H), (0, 0, 0, 0))
    # bloco inteiro entra de uma vez (slide up curto + fade); nada de palavra por palavra
    dx, dy, a = 0, 0, ease_out_cubic(min(1, (t - b["start"]) / 0.10))   # fade curto, igual em todos os blocos
    for i, tl in enumerate(b["tiles"]):
        tile = tl["accent"] if i == b["ki"] else tl["white"]
        img, pad, asc = tile
        paste(cv, tile, tl["x"] - pad + dx, tl["base"] - asc - pad + dy, a)
    return cv


# ---------- lettering ----------
# O lettering e SEMPRE a frase exata que ela fala (o bloco de legenda inteiro), nunca uma parafrase: o usuario
# reprovou "algo aproximado". job["letterings"] = [{"block": trecho que identifica o bloco, "main": palavras-chave}]
# -> pre (fina) / MAIN (bold, grande, azul) / pos (fina), no tempo exato do bloco; a legenda desse bloco some.
ftxt, fmain = font(92, CAP_W, CAP_FONT), font(150, KEY_W, KEY_FONT)
LET, HIDE = [], set()
for e in job.get("letterings", []):
    bi = next(i for i, b in enumerate(blocks) if e["block"].lower() in b["text"].lower())
    text = blocks[bi]["text"]
    k = text.lower().index(e["main"].lower())
    pre, main, pos = text[:k].strip(), text[k:k + len(e["main"])], text[k + len(e["main"]):].strip()
    # pontuacao solta ("," depois da palavra principal) virava uma linha so com a virgula, no meio da imagem
    pre, pos = ("" if not any(ch.isalnum() for ch in x) else x for x in (pre, pos))
    fm = fmain
    if KEY_STYLE == "plain":  # serifa italica: sem caixa alta, sem etiqueta, halo escuro para ler sobre a estante
        mt = main
    else:
        mt = main.upper()
    while fm.getlength(mt) > W - 260:
        fm = font(fm.size - 8, KEY_W, KEY_FONT)
    HIDE.add(bi)
    LET.append({"t": blocks[bi]["start"], "dur": max(1.6, blocks[bi]["end"] - blocks[bi]["start"]),
                "pre": text_tile(pre, ftxt, WHITE, glow=True) if pre else None, "pw": ftxt.getlength(pre),
                "main": text_tile(mt, fm, WHITE, glow=True) if KEY_STYLE == "plain" else pill_tile(mt, fm),
                "mw": fm.getlength(mt) + (0 if KEY_STYLE == "plain" else 2 * int(fm.size * 0.22)),
                "pos": text_tile(pos, ftxt, WHITE, glow=True) if pos else None, "sw": ftxt.getlength(pos)})


def let_frame(t):
    cur = [e for e in LET if e["t"] <= t < e["t"] + e["dur"]]
    if not cur:
        return None
    cv = Image.new("RGBA", (W, LB_H), (0, 0, 0, 0))
    for e in cur:
        dt = t - e["t"]
        fade_out = ease_out_cubic(min(1.0, (e["t"] + e["dur"] - t) / 0.30))
        # fade-in subindo, suave; linha de cima, palavra grande e linha de baixo entram em cascata curta
        rows = [(e["pre"], e["pw"], 250, 0.0, 40), (e["main"], e["mw"], 480, 0.08, 60), (e["pos"], e["sw"], 640, 0.16, 40)]
        for tile, w, base, delay, dist in rows:
            if tile is None:
                continue
            dx, dy, a = entrance(min(1, max(0, dt - delay) / 0.45), "up", dist)
            if a <= 0:
                continue
            img, pad, asc = tile
            paste(cv, tile, (W - w) / 2 - pad + dx, base - asc - pad + dy, a * fade_out)
    return cv


def encode(path, h, fn):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{h}",
                          "-r", "30000/1001", "-i", "-", "-c:v", "qtrle", "-pix_fmt", "argb", path], stdin=subprocess.PIPE)
    empty = Image.new("RGBA", (W, h), (0, 0, 0, 0)).tobytes()
    n = round(DUR * FPS)
    for i in range(n):
        fr = fn((i + 0.5) / FPS)
        p.stdin.write(empty if fr is None else fr.tobytes())
    p.stdin.close(); p.wait()
    return n


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("legenda:", encode(f"{OUT}/caps.mov", CB_H, caps_frame), "quadros")
    print("lettering:", encode(f"{OUT}/letter.mov", LB_H, let_frame), "quadros")
