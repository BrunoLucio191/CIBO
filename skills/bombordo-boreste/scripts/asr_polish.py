#!/usr/bin/env python3
"""Second pass on captions against what is ACTUALLY audible in each kept segment.

Run after plan.py (captions_<clip>.json exist) and before make_reels.py:

  JOB=job.json python3 asr_polish.py [clip ...]          # polish captions
  JOB=job.json python3 asr_polish.py --beats [clip ...]  # also re-place clicks/zooms

Why: the SRT is transcribed on the whole episode and cut afterwards, so each
segment edge can show a word that was trimmed away (phantom), miss a word that
is audible, and inherit whisper's sentence fragments ("Sou diagnóstica. Com
TDAH."). Each kept segment is re-transcribed on its own with the strong model
and the captions are aligned to it:
  * punctuation and casing follow the strong model (acronyms like CCO/TDAH kept);
  * unmatched caption words at a segment edge are dropped (phantoms);
  * audible words missing at a segment edge are added to the edge caption;
  * an immediate caption duplicate that the audio does not have is dropped;
  * any other disagreement is only REPORTED (fidelity: never rewrite speech on
    one model's word) in <work>/asr_polish_report.json.
--beats re-places click_times / impact_pulses / long_moves on emphasised
captions, because they are output-time and go stale whenever keeps move.
"""
import os, sys, json, re, subprocess, difflib, unicodedata

JOBF = os.environ['JOB']; JOB = json.load(open(JOBF))
B = os.environ.get('WORK', JOB.get('work', './work'))
SRCDIR = os.environ.get('SRCDIR', JOB['srcdir'])
MODEL = os.environ.get('ASR_MODEL', 'mlx-community/whisper-large-v3-mlx')
PROMPT = JOB.get('asr_prompt', 'Podcast em português brasileiro sobre o setor portuário.')
PUNCT = '.,?!…;:'

def norm(w):
    w = unicodedata.normalize('NFD', w.lower())
    w = ''.join(c for c in w if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9%]', '', w)

def apply_fix(w):
    for pat, rep in JOB.get('fix', []):
        w = re.sub(pat, rep, w, flags=re.I)
    return w

MODEL2 = os.environ.get('ASR_MODEL2', 'mlx-community/whisper-large-v3-turbo')
def transcribe(src, a, b, model=MODEL):
    # No domain prompt on purpose: a prompt about ports turned "no ponto" into
    # "no porto". Names/jargon are fixed afterwards by job.fix, not by biasing the ear.
    import mlx_whisper
    wav = os.path.join(B, '_seg.wav')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{a:.3f}', '-t', f'{b-a:.3f}',
                    '-i', src, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
    r = mlx_whisper.transcribe(wav, path_or_hf_repo=model, language='pt', word_timestamps=True,
                               condition_on_previous_text=False, verbose=None)
    return [apply_fix(w['word'].strip()) for s in r['segments'] for w in s.get('words', []) if w['word'].strip()]

def edge_actions(cn, an):
    """what the audio says about the first/last caption words: (drop_start, drop_end, add_start, add_end)"""
    ops = difflib.SequenceMatcher(None, cn, an, autojunk=False).get_opcodes()
    ds = de = 0; as_ = ae = ()
    if ops:
        t, i1, i2, j1, j2 = ops[0]
        if t in ('delete', 'replace') and i2 - i1 <= 2: ds = i2 - i1
        if t in ('insert', 'replace') and j2 - j1 <= 3: as_ = tuple(norm(x) for x in an[j1:j2])
        t, i1, i2, j1, j2 = ops[-1]
        if len(ops) > 1 or ops[0][0] != 'equal':
            if t in ('delete', 'replace') and i2 - i1 <= 2: de = i2 - i1
            if t in ('insert', 'replace') and j2 - j1 <= 3: ae = tuple(norm(x) for x in an[j1:j2])
    return ds, de, as_, ae

def style_like(cap_w, asr_w):
    core = cap_w.strip(PUNCT)
    tail = asr_w[len(asr_w.rstrip(PUNCT)):]
    a_core = asr_w.strip(PUNCT)
    if not (core.isupper() and len(core) >= 2):          # keep acronyms (CCO, TDAH)
        if a_core[:1].isupper(): core = core[:1].upper() + core[1:]
        else: core = core[:1].lower() + core[1:]
    return core + tail

def polish(k, P, report):
    c = P[k]; src = os.path.join(SRCDIR, c['src'])
    fp = os.path.join(B, f'captions_{k}.json'); D = json.load(open(fp)); caps = D['caps']
    emph = set(norm(w) for w in JOB.get('emph', '').split())
    off = 0.0; rep = []
    for si, (a, b) in enumerate(c['keeps']):
        dur = b - a
        idx = [i for i, cp in enumerate(caps) if off - 0.05 <= cp['s'] < off + dur - 0.02]
        toks = [(i, j) for i in idx for j in range(len(caps[i]['w']))]
        cw = [caps[i]['w'][j] for i, j in toks]
        aw = transcribe(src, a, b)                  # strong model: punctuation/casing source
        aw2 = transcribe(src, a, b, MODEL2)         # second opinion: edges change only if both agree
        cn, an, an2 = [norm(x) for x in cw], [norm(x) for x in aw], [norm(x) for x in aw2]
        sm = difflib.SequenceMatcher(None, cn, an, autojunk=False); ratio = sm.ratio()
        drop = set(); newtxt = {}; prepend = None; append = None
        if ratio >= 0.6 and toks:
            e1, e2 = edge_actions(cn, an), edge_actions(cn, an2)
            ds = min(e1[0], e2[0]); de = min(e1[1], e2[1])
            # jargon/acronyms (CCO, TDAH, emphasis terms) are misheard by BOTH models ("social"): never touch them
            prot = lambda w: (w.strip(PUNCT).isupper() and len(w.strip(PUNCT)) >= 2) or norm(w) in emph
            if ds and any(prot(w) for w in cw[:ds]): ds = 0; e1 = (0, e1[1], (), e1[3])
            if de and any(prot(w) for w in cw[-de:]): de = 0; e1 = (e1[0], 0, e1[2], ())
            if ds:
                for d in range(ds): drop.add(toks[d])
                rep.append(dict(seg=si, acao='removida_na_ponta', legenda=' '.join(cw[:ds])))
            if de and de < len(toks) - ds:
                for d in range(len(toks) - de, len(toks)): drop.add(toks[d])
                rep.append(dict(seg=si, acao='removida_na_ponta', legenda=' '.join(cw[-de:])))
            if e1[2] and e1[2] == e2[2]:
                prepend = [x for x in aw if norm(x)][:len(e1[2])]
                rep.append(dict(seg=si, acao='adicionada_na_ponta', audio=' '.join(prepend)))
            if e1[3] and e1[3] == e2[3]:
                append = aw[len(aw) - len(e1[3]):]
                rep.append(dict(seg=si, acao='adicionada_na_ponta', audio=' '.join(append)))
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == 'equal':
                    for d in range(i2 - i1):
                        newtxt[toks[i1 + d]] = style_like(cw[i1 + d], aw[j1 + d])
                elif tag == 'delete' and i2 - i1 == 1 and i1 > 0 and cn[i1] == cn[i1 - 1] and cn[i1:i2] != an2[j1:j1+1]:
                    drop.add(toks[i1]); rep.append(dict(seg=si, acao='duplicata_removida', legenda=cw[i1]))
                elif not ((i1 < ds) or (i2 > len(toks) - de)):
                    rep.append(dict(seg=si, acao='so_relatorio', tipo=tag, legenda=' '.join(cw[i1:i2]),
                                    audio=' '.join(aw[j1:j2]), audio2=' '.join(aw2[max(0,j1-1):j2+1])))
        else:
            rep.append(dict(seg=si, acao='alinhamento_fraco', similaridade=round(ratio, 3)))
        for i in idx:
            ws = []
            for j, w in enumerate(caps[i]['w']):
                if (i, j) in drop: continue
                ws.append(newtxt.get((i, j), w))
            caps[i]['w'] = ws
        if prepend and idx:
            f = idx[0]; caps[f]['w'] = [style_like(x, x) for x in prepend] + caps[f]['w']
        if append and idx:
            l = idx[-1]
            if caps[l]['w'] and caps[l]['w'][-1][-1:] in PUNCT and caps[l]['w'][-1][-1:] != ',':
                caps[l]['w'][-1] = caps[l]['w'][-1].rstrip(PUNCT)
            caps[l]['w'] = caps[l]['w'] + append
        off += dur
    out = []
    for cp in caps:
        if not cp['w']:
            if out and cp['e'] > out[-1]['e']: out[-1]['e'] = cp['e']
            continue
        cp['t'] = ' '.join(cp['w']); cp['em'] = [norm(w) in emph for w in cp['w']]; cp['any'] = any(cp['em'])
        out.append(cp)
    D['caps'] = out
    json.dump(D, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    report[k] = rep
    print(k, 'legendas:', len(out), '| mudanças:', sum(1 for r in rep if r['acao'] != 'so_relatorio'),
          '| só relatório:', sum(1 for r in rep if r['acao'] == 'so_relatorio'), flush=True)

def beats(k, P):
    caps = json.load(open(os.path.join(B, f'captions_{k}.json')))['caps']
    total = P[k]['total']
    cand = [cp for cp in caps if cp.get('any') and cp['s'] > 0.8 and cp['s'] < total - 1.5]
    picked = []
    for cp in cand:
        if all(abs(cp['s'] - p) >= max(7.0, total / 5) for p in picked): picked.append(round(cp['s'], 2))
        if len(picked) == 3: break
    clip = JOB['clips'][k]
    clip['click_times'] = picked
    clip['impact_pulses'] = [dict(t=t, amount=0.045, duration=1.1) for t in picked]
    gaps = sorted(set([0.0] + picked + [total]))
    mid = max(zip(gaps, gaps[1:]), key=lambda g: g[1] - g[0])
    clip['long_moves'] = [dict(t=round((mid[0] + mid[1]) / 2 - 1.4, 2), amount=0.03, duration=2.8)]
    print(k, 'beats em', picked, '->', [next((c['t'] for c in caps if abs(c['s']-t)<0.01),'?') for t in picked], flush=True)

if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    P = json.load(open(os.path.join(B, 'plan.json')))
    ks = args or list(P)
    report = {}
    rp = os.path.join(B, 'asr_polish_report.json')
    if os.path.exists(rp): report = json.load(open(rp))
    if '--beats-only' not in sys.argv:
        for k in ks: polish(k, P, report)
    json.dump(report, open(rp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if '--beats' in sys.argv or '--beats-only' in sys.argv:
        for k in ks: beats(k, P)
        json.dump(JOB, open(JOBF, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('relatório:', rp)
