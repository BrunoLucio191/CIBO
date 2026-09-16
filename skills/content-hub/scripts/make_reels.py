#!/usr/bin/env python3
"""Entry point. Usage:  JOB=job.json python3 make_reels.py [clip ...]"""
import os,sys,json,subprocess
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
JOBF=os.environ['JOB']; JOB=json.load(open(JOBF))
os.environ.setdefault('WORK',JOB.get('work','./work'))
os.environ.setdefault('SRCDIR',JOB['srcdir'])
os.environ.setdefault('FONT',JOB.get('font',os.path.join(HERE,'..','assets','CalSans-Regular.ttf')))
os.environ.setdefault('COVER_FONT',JOB.get('cover_font',os.path.join(HERE,'..','assets','Montserrat-VariableFont_wght.ttf')))
os.environ.setdefault('FILMBURN',JOB.get('filmburn',os.path.join(HERE,'..','assets','film_burn_clean.mp4')))
os.environ.setdefault('CLICK',JOB.get('click',os.path.join(HERE,'..','assets','click.wav')))
os.environ.setdefault('CLICK_GAIN',str(JOB.get('click_gain',0.11)))
os.environ.setdefault('WHOOSH',JOB.get('whoosh',os.path.join(HERE,'..','assets','whoosh_soft.wav')))
os.environ.setdefault('WHOOSH_GAIN',str(JOB.get('whoosh_gain',0.085)))
os.environ.setdefault('POP',JOB.get('pop',os.path.join(HERE,'..','assets','pop_low.wav')))
os.environ.setdefault('POP_GAIN',str(JOB.get('pop_gain',0.10)))
os.environ.setdefault('VIDEO_ENCODER',JOB.get('encoder','libx264'))
os.environ.setdefault('VT_BITRATE',str(JOB.get('vt_bitrate','16M')))
os.environ.setdefault('VT_MAXRATE',str(JOB.get('vt_maxrate','20M')))
os.environ.setdefault('VT_BUFSIZE',str(JOB.get('vt_bufsize','32M')))
os.environ.setdefault('LOGO',JOB.get('logo',os.path.join(HERE,'..','assets','logo_content_hub.png')))
os.environ.setdefault('COVER_LOGO',JOB.get('cover_logo',os.path.join(HERE,'..','assets','logo_content_hub_transparent.png')))
B=os.environ['WORK']; os.makedirs(B,exist_ok=True)
subprocess.run([sys.executable,os.path.join(HERE,'plan.py')],check=True,env=os.environ)
import render, cover, clicks as CK, render_caps as RC, render_lettering as RL
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
    cover_rev=fp(open(cover.__file__,encoding='utf-8').read())
    click_rev=fp(open(CK.__file__,encoding='utf-8').read())
    # fingerprint the caption DATA before render_caps decorates it with PIL objects
    CAPS=fp([{a:b for a,b in x.items() if a!='items'} for x in c['caps']])
    stage(f'caps:{k}',   fp(CAPS,JOB.get('style')), [f'{B}/caps_{k}_rgb.mp4',f'{B}/caps_{k}_a.mp4'],
          lambda: RC.render(c,f'{B}/caps_{k}'))
    lettering_rev=fp(open(RL.__file__,encoding='utf-8').read())
    lettering_key=fp(lettering_rev,c.get('letterings'),os.environ['COVER_FONT'])
    stage(f'lettering:{k}', lettering_key,
          [f'{B}/lettering_{k}_rgb.mp4',f'{B}/lettering_{k}_a.mp4'],
          lambda: RL.render(c,f'{B}/lettering_{k}'))
    clickkey=fp(click_rev,c.get('click_times'),[x['s'] for x in c['caps'] if x.get('any')],
                os.environ['CLICK'],os.environ['CLICK_GAIN'],os.environ['WHOOSH'],os.environ['WHOOSH_GAIN'],
                os.environ['POP'],os.environ['POP_GAIN'])
    stage(f'clicks:{k}',  clickkey, f'{B}/clicks_{k}.wav',
          lambda: CK.build(c,f'{B}/clicks_{k}.wav'))
    srcpath=os.path.join(os.environ['SRCDIR'],c['src'])
    srcsig=(os.path.getsize(srcpath),os.path.getmtime(srcpath))
    brollsig=[]
    for event in c.get('broll',[]):
        p=event['path']; brollsig.append((p,os.path.getsize(p),os.path.getmtime(p)))
    cutkey=fp(render_rev,c['keeps'],c['cropx'],c.get('cropx_timeline'),c.get('zoom_steps'),c.get('cropy'),c.get('cropy_steps'),c['src'],srcsig,c.get('impact_pulses'),c.get('long_moves'),c.get('grade'),c.get('broll'),brollsig)
    recut=stage(f'cut:{k}', cutkey, f'{B}/A_{k}.mp4', lambda: render.passA(c,f'{B}/A_{k}.mp4'))
    stage(f'intro:{k}',   cutkey, f'{B}/I_{k}.mp4', lambda: render.make_intro(f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4'))
    cover_key=fp(cover_rev,c['headline'],c['cover_t'],c.get('cover_cropx'),c.get('cover_logo_side'),c.get('keeps'),
                 os.environ['COVER_LOGO'],os.environ['COVER_FONT'])
    stage(f'cover:{k}',   cover_key, f'{B}/capa_{k}.png',
          lambda: cover.build(c,f'{B}/A_{k}.mp4',f'{B}/capa_{k}.png'))
    basename=c.get('filename',k)
    out=os.path.join(JOB.get('outdir',B),f'{basename}.mp4'); os.makedirs(os.path.dirname(out) or '.',exist_ok=True)
    def _final():
        render.final(c,f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4',out,cover=f'{B}/capa_{k}.png',
                     preset=JOB.get('preset','veryfast'),crf=JOB.get('crf',21),
                     extra=JOB.get('extra_v',''))
        import shutil; shutil.copy(f'{B}/capa_{k}.png',os.path.join(JOB.get('outdir',B),f'CAPA - {basename}.png'))
    stage(f'final:{k}', fp(render_rev,clickkey,cutkey,CAPS,lettering_key,cover_key,os.environ['FILMBURN'],c.get('music'),c.get('mix'),
                           os.environ['VIDEO_ENCODER'],os.environ['VT_BITRATE'],os.environ['VT_MAXRATE'],os.environ['VT_BUFSIZE'],
                           JOB.get('preset'),JOB.get('crf'),JOB.get('extra_v')), out, _final)
    print(k,'DONE ->',out,flush=True)
for k in (sys.argv[1:] or list(JOB['clips'])): run(k)
