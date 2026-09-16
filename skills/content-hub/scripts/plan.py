# -*- coding: utf-8 -*-
import os
import re, json, os, subprocess
import numpy as np

SRCDIR=os.environ.get('SRCDIR','.')
_ENV={}
def envelope(src):
    if src in _ENV: return _ENV[src]
    raw=subprocess.run(f'ffmpeg -v error -i "{SRCDIR}/{src}" -ac 1 -ar 8000 -f s16le -',
                       shell=True,capture_output=True).stdout
    a=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
    hop=80                      # 10 ms
    n=len(a)//hop
    e=np.sqrt(np.maximum(1e-9,(a[:n*hop]**2).reshape(n,hop).mean(1)))
    k=np.ones(3)/3.0
    e=np.convolve(e,k,mode='same')
    _ENV[src]=e; return e

def snap(src,t,win=0.16,mode='both'):
    """move a cut point to the quietest 10ms frame within +/-win seconds"""
    e=envelope(src); i=int(round(t*100))
    lo=max(0,i-int(win*100)); hi=min(len(e)-1,i+int(win*100))
    if hi<=lo: return t
    j=lo+int(np.argmin(e[lo:hi+1]))
    return round(j/100.0,3)


import os
JOB=json.load(open(os.environ['JOB']))
SRT=JOB['srt']
def sec(x):
    h,mn,rest=x.split(':');ss,ms=rest.split(',');return int(h)*3600+int(mn)*60+int(ss)+int(ms)/1000
GROUPS=[]
for b in re.split(r'\n\s*\n',open(SRT,encoding='utf-8').read().strip()):
    L=[x for x in b.strip().split('\n') if x.strip()]
    if len(L)<3: continue
    m=re.match(r'(\S+) --> (\S+)',L[1])
    if not m: continue
    GROUPS.append([sec(m.group(1)),sec(m.group(2)),re.sub('<[^>]+>','',' '.join(L[2:])).strip()])

CLIPS=JOB['clips']
_OLD={
 'corte01': dict(src='corte01_80porcento_HOST.mp4', master_in=708.866,
    headline='80% DE TUDO QUE\nEXISTE NO MUNDO\nPASSOU POR UM PORTO',
    cropx=0.50, cover_t=8.0,
    keeps=[(0.00,4.35),(5.00,6.50),(6.90,11.50),(12.28,18.40),(19.00,22.75),
           (23.10,28.05),(28.60,36.98),(37.42,42.55),(43.05,45.99),
           (48.90,53.06),(53.52,54.75),(55.02,55.93)]),
 'corte02': dict(src='corte02_gasolina_risco_HOST.mp4', master_in=2020.433,
    headline='A GASOLINA DO SEU\nCARRO PASSOU AQUI.\nE O RISCO?',
    cropx=0.50, cover_t=12.0,
    keeps=[(0.00,14.06),(14.52,20.36),(25.08,28.96),(29.42,32.06),
           (32.28,35.50),(36.62,39.26),(39.68,42.50),(43.00,51.00)]),
 'corte03': dict(src='src03.mp4', master_in=1566.700,
    headline='SEU SABONETE E SUA\nCOCA-COLA PASSARAM\nPELO MEU NAVIO',
    cropx=0.56, cover_t=30.0,
    keeps=[(0.10,9.10),(13.03,15.73),(16.20,17.53),(17.83,22.70),(23.10,25.66),
           (25.88,26.64),(30.18,33.20),(34.31,35.96),(37.38,38.93),
           (46.08,49.76),(50.45,52.56),(53.08,54.60),(55.01,59.23),
           (61.23,62.50),(62.98,64.26),(64.58,68.10)]),
}

# ---- text corrections applied to raw SRT text (regex -> replacement) ----
# Text corrections come from the job only. The old hardcoded list belonged to a
# ports episode of another client and rewrote unrelated words here.
FIX=[(a,b) for a,b in JOB.get('fix',[])]

# words that get the big/impact treatment
# Emphasis comes from the job only. The hardcoded list used to carry words from
# a different client's episode (portos/navios/gasolina), which leaked orange
# highlights into unrelated jobs.
EMPH = set(JOB.get('emph','').split())

def norm(w): return re.sub(r'[^0-9a-záàâãéêíóôõúüç%\-]','',w.lower())

def build(name):
    c=CLIPS[name]; mi=c['master_in']
    # local groups
    g=[]
    for s,e,t in GROUPS:
        ls,le=s-mi,e-mi
        if le<=0: continue
        g.append([ls,le,t])
    # keep-map: source time -> final time
    K=c['keeps']; keeps=[]
    for i,(a,b) in enumerate(K):
        a2=a if i==0 else snap(c['src'],a)
        b2=b if i==len(K)-1 else snap(c['src'],b)
        keeps.append((a2,b2))
    keeps=[(a,b) for a,b in keeps if b-a>0.25]
    c=dict(c); c['keeps']=keeps
    segs=[]; acc=0.0
    for a,b in keeps:
        segs.append((a,b,acc)); acc+=b-a
    total=acc
    def tofinal(t):
        for a,b,off in segs:
            if a-1e-6<=t<=b+1e-6: return off+(t-a)
        return None
    # caption atoms: split groups by keep windows
    atoms=[]
    for ls,le,t in g:
        for a,b,off in segs:
            s2,e2=max(ls,a),min(le,b)
            # 0.12s used to be the floor here, which threw away fast one-syllable
            # words ("não" measured exactly 0.120s and vanished from the caption,
            # inverting the sentence). Keep them; the merge step makes them legible.
            if e2-s2>0.02:
                txt=t
                for pat,rep in FIX: txt=re.sub(pat,rep,txt,flags=re.I)
                atoms.append([off+(s2-a),off+(e2-a),txt.strip()])
    atoms.sort()
    # split any atom whose whole SRT cue already exceeds the caption limit —
    # otherwise a long, unfragmented whisper segment ships as one on-screen
    # wall of text instead of the intended short auto-wrapped captions.
    _split=[]
    for a0,a1,txt in atoms:
        if len(txt)<=18:
            _split.append([a0,a1,txt]); continue
        words=txt.split(); chunks=[]; cur=[]; curlen=0
        for w in words:
            wl=len(w)+(1 if cur else 0)
            if curlen+wl>18 and cur:
                chunks.append(' '.join(cur)); cur=[w]; curlen=len(w)
            else:
                cur.append(w); curlen+=wl
        if cur: chunks.append(' '.join(cur))
        total_chars=sum(len(c) for c in chunks) or 1
        dur=a1-a0; t=a0
        for i,chunk in enumerate(chunks):
            frac=len(chunk)/total_chars
            c_end=a1 if i==len(chunks)-1 else t+dur*frac
            _split.append([t,c_end,chunk]); t=c_end
    atoms=_split
    # merge into <=18 char captions
    caps=[]
    for a in atoms:
        if caps:
            p=caps[-1]
            cand=(p[2]+' '+a[2]).replace('  ',' ').strip()
            cand=re.sub(r'\s+([,.?!])',r'\1',cand)
            if len(cand)<=18 and a[0]-p[1]<0.30 and (a[1]-p[0])<2.2:
                p[1]=a[1]; p[2]=cand; continue
        caps.append([a[0],a[1],a[2]])
    # second pass: absorb tiny orphan captions
    i=1
    while i<len(caps):
        if len(caps[i][2])<=4 and caps[i-1][1]-caps[i-1][0]<2.6 and len((caps[i-1][2]+' '+caps[i][2]))<=18:
            caps[i-1][1]=caps[i][1]; caps[i-1][2]=(caps[i-1][2]+' '+caps[i][2]).strip(); caps.pop(i); continue
        i+=1
    # tidy + emphasis
    out=[]
    for s,e,t in caps:
        t=re.sub(r'\s+',' ',t).strip().strip('-').strip()
        t=re.sub(r'\.\.\.$','...',t)
        if not t: continue
        if e-s<0.30: e=s+0.30
        for pat,rep in FIX: t=re.sub(pat,rep,t)
        ws=t.split(); flags=[norm(w) in EMPH for w in ws]
        out.append(dict(s=round(s,3),e=round(e,3),t=' '.join(ws),w=ws,em=flags,any=any(flags)))
    # de-overlap
    for i in range(len(out)-1):
        if out[i]['e']>out[i+1]['s']: out[i]['e']=out[i+1]['s']
    # A very short cue used to be dropped outright, which silently deleted fast
    # one-syllable words from the burned captions — including negations ("não"),
    # inverting the meaning of the sentence. Absorb them into a neighbour instead.
    out=[o for o in out if o['e']<=total+0.05]
    merged=[]
    for o in out:
        if o['e']-o['s']<=0.18 and (merged or True):
            host=merged[-1] if merged else None
            if host is not None and len(host['t'])+1+len(o['t'])<=22:
                host['t']=(host['t']+' '+o['t']).strip()
                host['w']=host['t'].split()
                host['em']=(host['em']+o['em'])[:len(host['w'])]
                host['any']=any(host['em'])
                host['e']=max(host['e'],o['e'])
                continue
            o=dict(o); o['e']=o['s']+0.19            # keep it, just make it legible
        merged.append(o)
    out=merged
    return dict(name=name, filename=c.get('filename',name), src=c['src'], keeps=keeps, total=round(total,3),
                headline=c['headline'], cropx=c['cropx'], cover_t=c['cover_t'],
                cover_cropx=c.get('cover_cropx',c.get('cropx',0.5)),
                cover_logo_side=c.get('cover_logo_side'),
                cropx_timeline=c.get('cropx_timeline',[]),
                zoom_steps=c.get('zoom_steps',[]), cropy=c.get('cropy',0.5),
                cropy_steps=c.get('cropy_steps',[]),
                grade=c.get('grade',{}), letterings=c.get('letterings',[]),
                broll=c.get('broll',[]),
                mix={**JOB.get('mix',{}), **c.get('mix',{})},
                music=c.get('music'), impact_pulses=c.get('impact_pulses',[]),
                long_moves=c.get('long_moves',[]),
                click_times=c.get('click_times',[]), caps=out,
                caption_base_y=c.get('caption_base_y'))

def externalise(B,P):
    """captions_<clip>.json is the human-editable source of truth.
       Regenerate only when REPLAN=1 or the file is missing."""
    scoped={x.strip() for x in os.environ.get('REPLAN_CLIPS','').split(',') if x.strip()}
    for k,v in P.items():
        fp=os.path.join(B,'captions_%s.json'%k)
        rebuild=os.environ.get('REPLAN')=='1' or k in scoped
        if os.path.exists(fp) and not rebuild:
            v['caps']=json.load(open(fp,encoding='utf-8'))['caps']
        else:
            json.dump({'clip':k,'total':v['total'],
                       'note':'edit t/w/em freely; s,e are seconds in the FINAL cut',
                       'caps':v['caps']},
                      open(fp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    return P

def review(B,P):
    import csv
    fp=os.path.join(B,'review.csv')
    with open(fp,'w',newline='',encoding='utf-8') as fh:
        w=csv.writer(fh); w.writerow(['clip','final_tc','final_s','text','emph'])
        for k,v in P.items():
            for c in v['caps']:
                t=c['s']+1/30  # one thumbnail frame at the head of the delivered file
                tc='%02d:%02d:%02d:%02d'%(t//3600,t%3600//60,t%60,round(t%1*30))
                w.writerow([k,tc,round(c['s'],2),c['t'],
                            ' '.join(x for x,f in zip(c['w'],c['em']) if f)])
    return fp

if __name__=='__main__':
    B=os.environ.get('WORK','.')
    P={k:build(k) for k in CLIPS}
    P=externalise(B,P)
    json.dump(P,open(os.path.join(B,'plan.json'),'w'),ensure_ascii=False,indent=1)
    print('review sheet:',review(B,P))
    for k,v in P.items():
        print('='*10,k,'total=%.2f'%v['total'],'caps=%d'%len(v['caps']))
        for c in v['caps']: print('  %6.2f %6.2f %-20s %s'%(c['s'],c['e'],c['t'],''.join('^' if f else '.' for f in c['em'])))
