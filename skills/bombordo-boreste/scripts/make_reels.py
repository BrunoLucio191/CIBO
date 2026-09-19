#!/usr/bin/env python3
"""Entry point. Usage:  JOB=job.json python3 make_reels.py [clip ...]"""
import os,sys,json,subprocess
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
JOBF=os.environ['JOB']; JOB=json.load(open(JOBF))
os.environ.setdefault('WORK',JOB.get('work','./work'))
os.environ.setdefault('SRCDIR',JOB['srcdir'])
os.environ.setdefault('FONT',JOB.get('font',os.path.join(HERE,'..','assets','CalSans-Regular.ttf')))
os.environ.setdefault('FILMBURN',JOB.get('filmburn',os.path.join(HERE,'..','assets','filmburn_blue.mp4')))
os.environ.setdefault('CLICK',JOB.get('click',''))
os.environ.setdefault('CLICK_GAIN',str(JOB.get('click_gain',0.11)))
os.environ.setdefault('VIDEO_ENCODER',JOB.get('encoder','libx264'))
os.environ.setdefault('VT_BITRATE',str(JOB.get('vt_bitrate','16M')))
os.environ.setdefault('VT_MAXRATE',str(JOB.get('vt_maxrate','20M')))
os.environ.setdefault('VT_BUFSIZE',str(JOB.get('vt_bufsize','32M')))
if JOB.get('logo'): os.environ.setdefault('LOGO',JOB['logo'])
B=os.environ['WORK']; os.makedirs(B,exist_ok=True)
subprocess.run([sys.executable,os.path.join(HERE,'plan.py')],check=True,env=os.environ)
import hashlib
def _canon_check():
    """A project-local COPY of the pipeline silently misses every later skill fix
    (ep3 shipped phantom captions and chopped words that the skill had already
    fixed). Warn loudly when the running scripts differ from the skill's."""
    for base in (os.path.expanduser('~/.claude/skills/bombordo-boreste/scripts'),):
        if os.path.isdir(base) and os.path.realpath(base)!=os.path.realpath(HERE):
            diff=[f for f in ('plan.py','render.py','clicks.py','render_caps.py','cover.py','make_reels.py')
                  if os.path.exists(os.path.join(base,f)) and os.path.exists(os.path.join(HERE,f))
                  and hashlib.sha1(open(os.path.join(base,f),'rb').read()).hexdigest()!=hashlib.sha1(open(os.path.join(HERE,f),'rb').read()).hexdigest()]
            print(f'!! ATENCAO: rodando uma COPIA do pipeline ({HERE}), nao a skill. Arquivos diferentes da skill: {diff or "nenhum"}. Rode direto de {base}.',flush=True)
_canon_check()
def _cut_report(only):
    P=json.load(open(os.path.join(B,'plan.json'))); bad=0
    for k in only:
        for a in P[k].get('cut_audit',[]):
            if a['where']=='in_speech':
                bad+=1; print(f"!! CORTE NO MEIO DA FALA: {k} seg{a['seg']} {a['edge']} em {a['to']:.2f}s (nenhuma pausa por perto)",flush=True)
            elif abs(a['to']-a['src_t'])>0.02 and a['where']=='pause':
                print(f"   corte ajustado p/ pausa: {k} seg{a['seg']} {a['edge']} {a['src_t']:.2f}->{a['to']:.2f}",flush=True)
    if bad and os.environ.get('STRICT_CUTS')=='1': raise SystemExit('STRICT_CUTS: cortes no meio da fala')
_cut_report(sys.argv[1:] or list(JOB['clips']))
import render, cover, clicks as CK, render_caps as RC
def sh(c):
    r=subprocess.run(c,shell=True,capture_output=True,text=True)
    if r.returncode: print(r.stderr[-2500:]); raise SystemExit(1)
STAMP=os.path.join(B,'.stamps.json')
_ST=json.load(open(STAMP)) if os.path.exists(STAMP) else {}
def fp(*parts):
    import hashlib
    return hashlib.sha1(json.dumps(parts,sort_keys=True,default=str).encode()).hexdigest()[:16]
def stage(name,key,out,fn):
    """run fn() only if its fingerprint or its output changed"""
    outs=out if isinstance(out,list) else [out]
    if _ST.get(name)==key and all(os.path.exists(o) for o in outs):
        print(name,'cached',flush=True); return False
    fn(); _ST[name]=key
    json.dump(_ST,open(STAMP,'w'),indent=1); print(name,'built',flush=True); return True

def run(k):
    P=json.load(open(os.path.join(B,'plan.json'))); c=P[k]
    render_rev=fp(open(render.__file__,encoding='utf-8').read())
    click_rev=fp(open(CK.__file__,encoding='utf-8').read())
    # fingerprint the caption DATA before render_caps decorates it with PIL objects
    CAPS=fp([{a:b for a,b in x.items() if a!='items'} for x in c['caps']])
    stage(f'caps:{k}',   fp(CAPS,JOB.get('style')), [f'{B}/caps_{k}_rgb.mp4',f'{B}/caps_{k}_a.mp4'],
          lambda: RC.render(c,f'{B}/caps_{k}'))
    clickkey=fp(click_rev,c.get('click_times'),[x['s'] for x in c['caps'] if x.get('any')],
                os.environ['CLICK'],os.environ['CLICK_GAIN'])
    stage(f'clicks:{k}',  clickkey, f'{B}/clicks_{k}.wav',
          lambda: CK.build(c,f'{B}/clicks_{k}.wav'))
    cutkey=fp(c['keeps'],c['cropx'],c.get('cropx_timeline'),c['src'],c.get('impact_pulses'),c.get('long_moves'),c.get('fade_out'))
    recut=stage(f'cut:{k}', cutkey, f'{B}/A_{k}.mp4', lambda: render.passA(c,f'{B}/A_{k}.mp4'))
    stage(f'intro:{k}',   cutkey, f'{B}/I_{k}.mp4', lambda: render.make_intro(f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4'))
    stage(f'cover:{k}',   fp(cutkey,c['headline'],c['cover_t']), f'{B}/capa_{k}.png',
          lambda: cover.build(c,f'{B}/A_{k}.mp4',f'{B}/capa_{k}.png'))
    basename=c.get('filename',k)
    out=os.path.join(JOB.get('outdir',B),f'{basename}.mp4'); os.makedirs(os.path.dirname(out) or '.',exist_ok=True)
    def _final():
        render.final(c,f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4',out,cover=f'{B}/capa_{k}.png',
                     preset=JOB.get('preset','veryfast'),crf=JOB.get('crf',21),
                     extra=JOB.get('extra_v',''))
        import shutil; shutil.copy(f'{B}/capa_{k}.png',os.path.join(JOB.get('outdir',B),f'CAPA - {basename}.png'))
    stage(f'final:{k}', fp(render_rev,clickkey,cutkey,CAPS,c['headline'],c['cover_t'],os.environ['FILMBURN'],c.get('music'),c.get('mix'),
                           os.environ['VIDEO_ENCODER'],os.environ['VT_BITRATE'],os.environ['VT_MAXRATE'],os.environ['VT_BUFSIZE'],
                           JOB.get('preset'),JOB.get('crf'),JOB.get('extra_v')), out, _final)
    print(k,'DONE ->',out,flush=True)
for k in (sys.argv[1:] or list(JOB['clips'])): run(k)
