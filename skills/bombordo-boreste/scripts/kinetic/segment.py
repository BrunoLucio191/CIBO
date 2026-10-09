"""Etapa 2 — blocks of 1..4 words and destaques.

Rules: break on sentence punctuation and on pauses; never end a block on an
article/preposition/conjunction (it stays with the word it introduces); max 4
words / max_chars. Destaques: numbers and values, the job's emphasis terms,
emotion words, strong verbs; about one every `highlight_every` blocks, never two
blocks in a row. A destaque is shown alone and big; a leading function word
("de", "a") rides with it in small type so it is never separated.
Output: <work>/kinetic/blocks_<clip>.json (editable: move words, flip `hl`, change `preset`).
"""
import os, re
from collections import Counter
from common import norm, kdir, jload, jsave

FUNC = set('o a os as um uma uns umas de do da dos das em no na nos nas num numa por pelo pela pelos pelas à às '
           'para pra pro pros pras com sem sob sobre até ao aos e ou mas que se me te lhe lhes nem '
           'meu minha meus minhas seu sua seus suas nosso nossa teu tua'.split())
UNITS = set('anos ano % por cento mil milhoes milhao bilhoes telas funcionarios pessoas vezes dias meses horas reais'.split())
MONTHS = set('janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro dezembro'.split())
EMOTION = set('apaixonada apaixonado amor medo orgulho loucura confusao choque desafio bizarro incrivel absurdo '
              'dificil feliz triste raiva coragem sonho sonhos forte fracasso sucesso duvidaram duvidou preconceito '
              'unica unico primeira primeiro nunca jamais sempre'.split())
STRONG = set('arrombar liderar lidera liderei assumi assumiu virei transformou transformar conquistar conquistei '
             'enfrentar enfrentei desisti desistir mudou mudar provar provei venci vencer abrir'.split())
PUNCT_END = re.compile(r'[.!?;:…]$')
# generic words never carry a destaque (speech verbs, fillers, vague nouns)
WEAK = set('falou falei disse dizer assim ainda coisa coisas gente galera empresa precisar precisava menor maior tipo '
           'entao aqui ali agora hoje sempre muito muita pouco tambem porque quando onde isso isto esse essa '
           'tinha tenho estava estou ficar fazer faz fiz vai vou ia era foi sou ser estar tava ter'.split())


def is_num(w): return bool(re.search(r'\d', w))


def low(w):
    """lower-case, punctuation stripped, ACCENTS KEPT (é != e, à != a in meaning here)"""
    return re.sub(r'[^\wà-ÿ%]', '', w.lower())


def is_func(w): return low(w) in FUNC


def base_blocks(words, cfg):
    sg = cfg['segmentation']; out = []; cur = []
    def flush():
        nonlocal cur
        if cur: out.append(cur); cur = []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        gap = (nxt['s'] - w['e']) if nxt else 9
        chars = len(' '.join(words[k]['w'] for k in cur))
        hard = PUNCT_END.search(w['w']) or gap > sg['pause_break'] or nxt is None
        soft = w['w'].endswith(',')
        full = len(cur) >= sg['max_words'] or (nxt and chars + 1 + len(nxt['w']) > sg['max_chars'])
        if hard or soft or full:
            if not hard and is_func(w['w']) and len(cur) > 1:   # never strand an article/preposition
                cur.pop(); flush(); cur = [i]
                continue
            flush()
    flush()
    return out


def score(words, i, emph):
    w = norm(words[i]['w'])
    if not w or is_func(words[i]['w']): return 0
    if w in WEAK: return 0
    s = 0.6 if len(w) >= 5 else 0.0                              # any content word can carry a beat
    if is_num(words[i]['w']): s += 3
    if w in emph: s += 2.2
    if w in EMOTION: s += 1.8
    if w in STRONG: s += 1.6
    if len(w) >= 8: s += 0.3
    if PUNCT_END.search(words[i]['w']): s += 0.4               # end of a thought
    return s


PROPER = set('larissa juliana daniel tegram itaqui sindop sindomar cco tdah inpasa loginpex sousa frazao brasil '
             'wilson sons vale petrobras antaq emap alumar suzano maranhao sao luis'.split())

NOT_NAME = set('eu ele ela eles elas você vocês voce voces nós nos isso isto aquilo então entao aí ai mas foi era é '
               'não nao sim olha cara tipo hoje depois quando porque'.split())


def display(words, proper=()):
    """On-screen text: punctuation is used to split blocks, not shown (only ? and !);
    mid-sentence capitals left by whisper fragments ("Com TDAH", "Fazer.") go lower-case.
    A capital is KEPT (it is a name) when the word is in PROPER / kinetic.yaml `proper`,
    when it is capitalised mid-sentence 2+ times and never written lower-case in the clip
    ("entrei na Wilson"), or when it touches another mid-sentence capital ("Wilson Sons")."""
    names = PROPER | {norm(p) for p in proper}
    # sentence openers the SRT capitalises without a full stop ("na Wilson / Eu trabalhei")
    opener = lambda raw: is_func(raw) or low(raw) in NOT_NAME
    core_of = lambda raw: raw.rstrip('.,;:…')
    mid, prev_end = [], True
    for w in words:
        c = core_of(w['w']); mid.append(bool(c) and c[0].isupper() and not prev_end and not c.isupper())
        prev_end = bool(PUNCT_END.search(w['w']))
    lower_seen = {low(w['w']) for w in words if core_of(w['w'])[:1].islower()}
    caps_mid = Counter(low(w['w']) for w, m in zip(words, mid) if m)
    for i, w in enumerate(words):
        raw = w['w']; core = core_of(raw)
        if mid[i] and not opener(raw):
            pair = any(0 <= j < len(words) and mid[j] and not opener(words[j]['w']) for j in (i - 1, i + 1))
            if norm(core) in names or pair or (caps_mid[low(raw)] >= 2 and low(raw) not in lower_seen):
                w['d'] = core; continue
        if mid[i] and norm(core) not in names:
            core = core[0].lower() + core[1:]
        w['d'] = core if core else raw
    return words


def build(job, work, clip, cfg):
    W = jload(os.path.join(kdir(work), f'words_{clip}.json'))
    merged = []                                   # "quarta -feira", "e -mail": Whisper separa o hífen
    for w in W['words']:
        if merged and w['w'].startswith('-'):
            merged[-1] = dict(merged[-1], w=merged[-1]['w'] + w['w'], e=w['e']); continue
        merged.append(w)
    W['words'] = merged
    words = display(W['words'], cfg.get('proper', []))
    emph = set(norm(x) for x in job.get('emph', '').split())
    blocks = base_blocks(words, cfg)
    cand = []
    for bi, blk in enumerate(blocks):
        best = max(blk, key=lambda i: score(words, i, emph))
        if score(words, best, emph) >= 0.6: cand.append((score(words, best, emph), bi, best))
    units = []
    curated = cfg.get('highlights')
    if curated:                                   # chosen by meaning (kinetic.yaml videos.<clip>.highlights)
        pos = 0; nw = [norm(w['w']) for w in words]
        for ph in curated:
            toks = [norm(x) for x in str(ph).split() if norm(x)]   # YAML reads a bare 80 as int
            for i in range(pos, len(nw) - len(toks) + 1):
                if nw[i:i + len(toks)] == toks:
                    j = i + len(toks) - 1
                    if is_num(words[j]['w']) and j + 1 < len(words) and words[j + 1]['w'].strip() == '%': j += 1
                    units.append((i, j)); pos = j + 1; break
            else:
                print(f'   aviso: destaque "{ph}" não encontrado em ordem no texto', flush=True)
    else:
        target = max(1, round(len(blocks) / cfg['segmentation']['highlight_every']))
        chosen = {}; used = set()
        for sc, bi, wi in sorted(cand, reverse=True):
            if norm(words[wi]['w']) in used: continue
            if len(chosen) >= target: break
            if any(abs(bi - b) <= cfg['segmentation']['min_blocks_between_highlights'] for b in chosen): continue
            chosen[bi] = wi; used.add(norm(words[wi]['w']))
        for wi in sorted(chosen.values()):
            j = wi
            if is_num(words[wi]['w']) and wi + 1 < len(words) and (norm(words[wi + 1]['w']) in UNITS
                                                                  or words[wi + 1]['w'].strip() == '%'): j = wi + 1   # "100 %" stays one unit
            if (is_num(words[wi]['w']) and wi + 2 < len(words) and low(words[wi + 1]['w']) == 'de'
                    and norm(words[wi + 2]['w']) in MONTHS): j = wi + 2          # "7 de setembro"
            units.append((wi, j))
    unit_of = {i: u for u, (a0, b0) in enumerate(units) for i in range(a0, b0 + 1)}
    final = []
    for blk in blocks:
        run = []
        for i in blk:
            if i not in unit_of:
                run.append(i); continue
            u = unit_of[i]
            if final and final[-1]['kind'] == 'highlight' and final[-1]['u'] == u and not run:
                final[-1]['idx'].append(i); continue
            lead = []                                     # an article/preposition rides with its word
            while run and is_func(words[run[-1]]['w']) and len(lead) < 2: lead.insert(0, run.pop())
            if run: final.append(dict(kind='normal', idx=run)); run = []
            final.append(dict(kind='highlight', idx=lead + [i], small=lead, u=u))
        if run: final.append(dict(kind='normal', idx=run))
    # a block on screen for less than ~0.35 s reads as a flash: fold it into the next one
    # (or ride small in front of the next destaque)
    merged = []
    for n, b in enumerate(final):
        nxt = final[n + 1] if n + 1 < len(final) else None
        if b['kind'] == 'normal' and nxt is not None:
            span = words[nxt['idx'][0]]['s'] - words[b['idx'][0]]['s']
            if span < 0.35:
                if nxt['kind'] == 'normal' and len(b['idx']) + len(nxt['idx']) <= cfg['segmentation']['max_words'] + 1:
                    nxt['idx'] = b['idx'] + nxt['idx']; continue
                # only an article/preposition may ride small above a destaque; a word that ends a
                # sentence ("o que isso quer dizer?" + "Poucas empresas") goes back to its own phrase
                ends = words[b['idx'][-1]]['w'].rstrip().endswith(('.', '?', '!'))
                if (nxt['kind'] == 'highlight' and len(nxt.get('small', [])) + len(b['idx']) <= 2
                        and not ends and all(is_func(words[i]['w']) for i in b['idx'])):
                    nxt['idx'] = b['idx'] + nxt['idx']; nxt['small'] = b['idx'] + nxt.get('small', []); continue
                if merged and merged[-1]['kind'] == 'normal':
                    merged[-1]['idx'] += b['idx']; continue
        merged.append(b)
    final = merged
    # presets: slide_blur anchors the style; drop_blur opens a new sentence after a pause,
    # mask_reveal for a longer block; never the same accent preset twice in a row
    out = []; last_norm = last_hl = None; hl_presets = cfg['presets']['highlight']; hcount = 0
    for n, b in enumerate(final):
        ws = [dict(w=words[i]['d'], raw=words[i]['w'], s=words[i]['s'], e=words[i]['e'], small=(i in b.get('small', [])),
                   hl=(b['kind'] == 'highlight' and i not in b.get('small', []))) for i in b['idx']]
        for k in range(len(ws) - 1, 0, -1):          # "100 %" -> "100%" (Whisper splits the sign off)
            if ws[k]['w'].strip() == '%' and is_num(ws[k - 1]['w']):
                ws[k - 1]['w'] += '%'; ws[k - 1]['raw'] += '%'; ws[k - 1]['e'] = ws[k]['e']; del ws[k]
        if b['kind'] == 'highlight':
            preset = hl_presets[hcount % len(hl_presets)]; hcount += 1
        else:
            prev_end = out[-1]['words'][-1]['e'] if out else -9
            prev_txt = out[-1]['words'][-1]['w'] if out else '.'
            new_sentence = PUNCT_END.search(prev_txt) and ws[0]['s'] - prev_end > 0.35
            preset = 'slide_blur'
            if new_sentence and last_norm != 'drop_blur': preset = 'drop_blur'
            elif len(ws) >= 3 and last_norm not in ('mask_reveal',) and n % 4 == 3: preset = 'mask_reveal'
            last_norm = preset
        out.append(dict(id=n, kind=b['kind'], preset=preset, words=ws))
    nh = sum(1 for b in out if b['kind'] == 'highlight')
    res = dict(clip=clip, note='edite: mova palavras entre blocos, troque hl true/false, preset em '
               + str(cfg['presets']), blocks=out)
    p = os.path.join(kdir(work), f'blocks_{clip}.json'); jsave(res, p)
    print(f"{clip}: {len(out)} blocos, {nh} destaques (1 a cada {len(out)/max(1,nh):.1f}) -> {p}", flush=True)
    return res
