"""Etapa 1 — word-level timing for one cut.

Reference TEXT = the reviewed captions (captions_<clip>.json, already corrected);
TIMING = mlx_whisper large-v3 word timestamps on the cut's own voice track
(A_<clip>.mp4, before music), aligned to the reference with difflib, then each
word start snapped to the real voice onset in the audio envelope.
Output: <work>/kinetic/words_<clip>.json (editable: w, s, e per word).
"""
import os, re, subprocess, difflib
import numpy as np
from common import norm, kdir, jload, jsave

MODEL = os.environ.get('KIN_ASR_MODEL', 'mlx-community/whisper-large-v3-mlx')


def voice_wav(work, clip):
    out = os.path.join(kdir(work), f'voice_{clip}.wav')
    src = os.path.join(work, f'A_{clip}.mp4')
    # re-extract whenever the cut changed: a stale voice_<clip>.wav from an older keeps
    # left half the words without audio timing (ep04: 46/93 after re-cutting corte01)
    if not os.path.exists(out) or os.path.getmtime(src) > os.path.getmtime(out):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', src,
                        '-vn', '-ac', '1', '-ar', '16000', out], check=True)
    return out


def envelope(wav):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', wav, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                       capture_output=True).stdout
    a = np.frombuffer(r, dtype='<i2').astype(np.float32) / 32768
    n = len(a) // 160
    e = np.sqrt((a[:n * 160] ** 2).reshape(n, 160).mean(1))      # 10 ms frames
    return np.convolve(e, np.ones(3) / 3, mode='same')


def asr_words(wav):
    import mlx_whisper
    r = mlx_whisper.transcribe(wav, path_or_hf_repo=MODEL, language='pt', word_timestamps=True,
                               condition_on_previous_text=False, verbose=None)
    return [(w['word'].strip(), float(w['start']), float(w['end'])) for s in r['segments'] for w in s.get('words', [])
            if w['word'].strip()]


def snap_onset(env, s, before=0.10, after=0.08):
    """First rise into voice near s. Whisper starts drift +-0.1..0.2 s; the entry
    must lead the sound by 1-2 frames, so the real onset matters."""
    i0, i1 = max(1, int((s - before) * 100)), min(len(env) - 1, int((s + after) * 100))
    if i1 <= i0: return s
    seg = env[i0:i1 + 1]
    floor = float(np.percentile(env[max(0, i0 - 30):i1 + 30], 10))
    peak = float(env[i0:min(len(env), i1 + 25)].max())
    thr = floor + 0.3 * (peak - floor)
    for k in range(1, len(seg)):
        if seg[k] >= thr and seg[k - 1] < thr:
            return round((i0 + k - 1) / 100.0, 3)
    return s


def raw_srt_words(job, clip, plan):
    """The untouched whisper text inside this cut (for the corrections list)."""
    srt = job['srt'] if os.path.isabs(job['srt']) else os.path.join(os.path.dirname(os.path.abspath(os.environ['JOB'])), job['srt'])
    mi = job['clips'][clip]['master_in']
    cues = []
    for b in re.split(r'\n\s*\n', open(srt, encoding='utf-8').read().strip()):
        L = [x for x in b.strip().split('\n') if x.strip()]
        if len(L) < 3: continue
        m = re.match(r'(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)', L[1])
        if not m: continue
        g = list(map(int, m.groups()))
        cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000 - mi, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000 - mi, ' '.join(L[2:])))
    words = []
    for a, b in plan['keeps']:
        for s, e, t in cues:
            if min(e, b) - max(s, a) > 0.12: words += t.split()
    return words


def build(job, work, clip):
    plan = jload(os.path.join(work, 'plan.json'))[clip]
    caps = jload(os.path.join(work, f'captions_{clip}.json'))['caps']
    ref = [dict(w=w, cap=i, cs=c['s'], ce=c['e']) for i, c in enumerate(caps) for w in c['w']]
    wav = voice_wav(work, clip); env = envelope(wav)
    asr = asr_words(wav)
    rn, an = [norm(r['w']) for r in ref], [norm(a[0]) for a in asr]
    sm = difflib.SequenceMatcher(None, rn, an, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for d in range(i2 - i1):
                r, a = ref[i1 + d], asr[j1 + d]
                if r['cs'] - 0.6 <= a[1] <= r['ce'] + 0.6:
                    r['s'], r['e'], r['src'] = a[1], a[2], 'asr'
    # interpolate words the ear did not confirm, inside their caption window
    i = 0
    while i < len(ref):
        if 'src' in ref[i]: i += 1; continue
        j = i
        while j < len(ref) and 'src' not in ref[j] and ref[j]['cap'] == ref[i]['cap']: j += 1
        lo = ref[i - 1]['e'] if i > 0 and 'src' in ref[i - 1] and ref[i - 1]['cap'] == ref[i]['cap'] else ref[i]['cs']
        hi = ref[j]['s'] if j < len(ref) and 'src' in ref[j] and ref[j]['cap'] == ref[i]['cap'] else ref[i]['ce']
        hi = max(hi, lo + 0.12 * (j - i))
        tot = sum(len(ref[k]['w']) + 1 for k in range(i, j)); t = lo
        for k in range(i, j):
            d = (hi - lo) * (len(ref[k]['w']) + 1) / tot
            ref[k]['s'], ref[k]['e'], ref[k]['src'] = round(t, 3), round(t + d, 3), 'interp'; t += d
        i = j
    for r in ref:
        if r['src'] == 'asr': r['s'] = snap_onset(env, r['s'])
    for k in range(len(ref)):                      # monotonic, no overlaps, minimum length
        if k and ref[k]['s'] < ref[k - 1]['s'] + 0.04: ref[k]['s'] = round(ref[k - 1]['s'] + 0.04, 3)
        ref[k]['e'] = round(max(ref[k]['e'], ref[k]['s'] + 0.08), 3)
        if k + 1 < len(ref): ref[k]['e'] = round(min(ref[k]['e'], max(ref[k + 1]['s'], ref[k]['s'] + 0.04)), 3)
    words = [dict(w=r['w'], s=round(r['s'], 3), e=round(r['e'], 3), src=r['src']) for r in ref]
    raw = raw_srt_words(job, clip, plan)
    corr = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [norm(x) for x in raw], rn, autojunk=False).get_opcodes():
        if tag != 'equal':
            a, b = ' '.join(raw[i1:i2]), ' '.join(r['w'] for r in ref[j1:j2])
            if norm(a) != norm(b): corr.append(dict(transcricao=a, legenda=b))
    div = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != 'equal':
            div.append(dict(legenda=' '.join(r['w'] for r in ref[i1:i2]), ouvido=' '.join(a[0] for a in asr[j1:j2])))
    out = dict(clip=clip, total=plan['total'], note='edite w/s/e à vontade (segundos no vídeo final, sem a capa)',
               words=words, correcoes=corr, divergencias_asr=div,
               confirmadas_asr=sum(1 for r in ref if r['src'] == 'asr'), total_palavras=len(ref))
    p = os.path.join(kdir(work), f'words_{clip}.json'); jsave(out, p)
    print(f"{clip}: {out['confirmadas_asr']}/{len(ref)} palavras com tempo do áudio, {len(corr)} correções vs SRT -> {p}", flush=True)
    return out
