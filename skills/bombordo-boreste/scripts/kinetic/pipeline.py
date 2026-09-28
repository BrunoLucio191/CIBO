"""Render / preview / export: runs the normal make_reels pipeline with the kinetic
caption layer swapped in, then exports with the ORIGINAL deliverable's audio
stream copied untouched (no re-encode) into a new folder.
"""
import os, sys, json, copy, subprocess, shutil
from common import kdir, jload, jsave
import align, segment
import kinrender

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
FPS = 30


def ensure_data(job, work, clip, cfg):
    kd = kdir(work)
    if not os.path.exists(os.path.join(kd, f'words_{clip}.json')): align.build(job, work, clip)
    bp = os.path.join(kd, f'blocks_{clip}.json')
    if not os.path.exists(bp): segment.build(job, work, clip, cfg)
    return bp


def derived_job(job, jobf, work, clip, cfg, blocks_path, outdir):
    kw = os.path.join(kdir(work), 'render'); os.makedirs(kw, exist_ok=True)
    J = copy.deepcopy(job); c = J['clips'][clip]
    J['work'] = kw; J['outdir'] = outdir; J['crf'] = 18; J['preset'] = 'medium'; J.pop('encoder', None)
    c['caption_engine'] = 'kinetic'; c['kinetic_blocks'] = blocks_path; c['kinetic_cfg'] = cfg
    c['cap_band_h'] = cfg['position']['band_height']
    if cfg['punch_in']['enabled']:
        blocks = jload(blocks_path)['blocks']
        c['impact_pulses'] = [dict(t=round(max(0.3, b['words'][0]['s'] - cfg['timing']['lead']), 2),
                                   amount=cfg['punch_in']['amount'], duration=cfg['punch_in']['duration'])
                              for b in blocks if b['kind'] == 'highlight']
    else:
        c['impact_pulses'] = []
    J['clips'] = {clip: c}
    src_caps = os.path.join(work, f'captions_{clip}.json')
    if os.path.exists(src_caps): shutil.copy(src_caps, os.path.join(kw, f'captions_{clip}.json'))
    jf = os.path.join(kw, f'job_{clip}.json'); jsave(J, jf)
    return jf, kw


def run_make_reels(jf, root, clip, encoder=None):
    env = {k: v for k, v in os.environ.items() if k not in ('WORK', 'SRCDIR', 'REPLAN', 'REPLAN_CLIPS', 'VIDEO_ENCODER')}
    env['JOB'] = jf
    if encoder: env.update(VIDEO_ENCODER=encoder, VT_BITRATE='14M', VT_MAXRATE='18M')
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'make_reels.py'), clip], cwd=root, env=env,
                       capture_output=True, text=True)
    if r.returncode: print(r.stdout[-2000:], r.stderr[-3000:]); raise SystemExit('make_reels falhou')
    for line in r.stdout.splitlines():
        if any(x in line for x in ('DONE', '!!', 'built')): print('  ', line)


def export(job, root, clip, outdir):
    """Swap in the original deliverable's audio stream bit-for-bit (-c:a copy)."""
    name = job['clips'][clip].get('filename', clip)
    new = os.path.join(outdir, f'{name}.mp4')
    orig = os.path.join(root, job.get('outdir', './work'), f'{name}.mp4')
    tmp = os.path.join(outdir, f'.{clip}_mux.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', new, '-i', orig, '-map', '0:v:0', '-map', '1:a:0',
                    '-c', 'copy', '-movflags', '+faststart', tmp], check=True)
    os.replace(tmp, new)
    cap = os.path.join(outdir, f'CAPA - {name}.png')
    if os.path.exists(cap): os.replace(cap, os.path.join(outdir, f'{name} - CAPA.png'))
    dv = lambda f, s: float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', s, '-show_entries',
                                            'stream=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.split()[0])
    print(f'   exportado: {new}  (vídeo {dv(new, "v:0"):.2f}s, áudio original copiado {dv(new, "a:0"):.2f}s)')
    return new


def render(job, jobf, work, clip, cfg):
    root = os.path.dirname(jobf)
    outdir = os.path.join(root, job.get('kinetic_outdir', './codex_reels/deliverables/kinetic'))
    os.makedirs(outdir, exist_ok=True)
    bp = ensure_data(job, work, clip, cfg)
    jf, kw = derived_job(job, jobf, work, clip, cfg, bp, outdir)
    run_make_reels(jf, root, clip)
    return export(job, root, clip, outdir)


def preview(job, jobf, work, clip, cfg, start, dur):
    root = os.path.dirname(jobf); kd = kdir(work)
    pv = os.path.join(kd, 'preview_out'); os.makedirs(pv, exist_ok=True)
    bp = ensure_data(job, work, clip, cfg)
    jf, kw = derived_job(job, jobf, work, clip, cfg, bp, pv)
    run_make_reels(jf, root, clip, encoder='h264_videotoolbox')
    name = job['clips'][clip].get('filename', clip)
    full = os.path.join(pv, f'{name}.mp4'); out = os.path.join(kd, f'preview_{clip}.mp4')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-ss', f'{start:.3f}', '-t', f'{dur:.3f}', '-i', full,
                    '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', out], check=True)
    sheet(bp, cfg, full, os.path.join(kd, f'preview_{clip}_sheet.jpg'), start, start + dur, job['clips'][clip])
    print('   prévia:', out)
    return out


def sheet(bp, cfg, video, out, t0, t1, clipcfg):
    """Frames at entries, destaques and exits inside the window, labelled."""
    import cv2, numpy as np
    blocks = [b for b in jload(bp)['blocks'] if b['words']]
    kinrender.timeline(blocks, cfg, 9999)
    lead = 1.0 / FPS                                   # the cover frame precedes the body
    moments = []
    for b in blocks:
        if not (t0 <= b['t_in'] <= t1): continue
        txt = ' '.join(w['w'] for w in b['words'])[:22]
        if b['kind'] == 'highlight':
            moments += [(b['t_in'] + 0.06, f'destaque in {txt}'), (b['t_in'] + 0.35, f'destaque {txt}')]
        else:
            moments += [(b['t_in'] + 0.07, f"entrada {b['preset']}"), (b['words'][-1]['s'] + 0.05, f'ativa {txt}')]
        moments.append((b['t_out'] + b.get('exit_dur', 0.15) * 0.5, 'saida'))
    moments = sorted(m for m in moments if t0 <= m[0] <= t1)[:16]
    tiles = []
    for t, lab in moments:
        r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t + lead:.3f}', '-i', video, '-frames:v', '1',
                            '-vf', 'scale=270:480', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'], capture_output=True).stdout
        if len(r) < 270 * 480 * 3: continue
        im = np.frombuffer(r, np.uint8).reshape(480, 270, 3).copy()
        cv2.rectangle(im, (0, 0), (270, 34), (0, 0, 0), -1)
        cv2.putText(im, f'{t:.2f}s', (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 255, 255), 1)
        import unicodedata
        lab = ''.join(c for c in unicodedata.normalize('NFD', lab) if unicodedata.category(c) != 'Mn')
        cv2.putText(im, lab[:34], (4, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (255, 255, 255), 1)
        tiles.append(im)
    while len(tiles) % 4: tiles.append(np.zeros((480, 270, 3), np.uint8))
    cv2.imwrite(out, np.vstack([np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]))
    print('   folha de contatos:', out)
