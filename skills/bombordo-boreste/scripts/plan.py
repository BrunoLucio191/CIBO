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

PAUSE_THR=float(os.environ.get('PAUSE_THR','0.02'))   # speech median is ~0.06, room floor ~0.002
def pause_runs(src,lo,hi,minf=5):
    """runs of >=50 ms below PAUSE_THR: the only places a cut cannot chop a word"""
    e=envelope(src); i0=max(0,int(lo*100)); i1=min(len(e),int(hi*100)+1)
    runs=[]; i=i0
    while i<i1:
        if e[i]<PAUSE_THR:
            j=i
            while j<i1 and e[j]<PAUSE_THR: j+=1
            if j-i>=minf: runs.append((i/100.0,j/100.0))
            i=j
        else: i+=1
    return runs

def place(src,t,kind,last=False,fwd=0.6,back=0.45):
    """Put a cut boundary inside a REAL pause instead of wherever it was authored.

    The old rule (quietest 10 ms frame within +/-160 ms, and never touching the
    first start / last end) cut words in half whenever no pause sat that close,
    and the last end also runs under a 120 ms fade-out that ate the tail of the
    final word. END now completes the word being spoken (next pause after t);
    START now includes the whole word being spoken (previous pause before t).
    Returns (t2, info); info['where']=='in_speech' means no pause was found."""
    runs=pause_runs(src,t-back-0.7,t+fwd+0.7)
    info=dict(src_t=round(t,3),where='pause',room=None,sil_start=None)
    inside=[r for r in runs if r[0]-0.005<=t<=r[1]+0.005]
    runs=[r for r in runs if r[1]-r[0]>=0.08]   # stop-consonant closures inside a word are ~50-70 ms: not a pause
    if kind=='end':
        need=0.12 if last else 0.03
        if inside: r=inside[0]
        else:
            nxt=[r for r in runs if t-0.10<=r[0]<=t+fwd]
            prv=[r for r in runs if t-back<=r[1]<=t+0.02]
            r=min(nxt,key=lambda r:r[0]) if nxt else (max(prv,key=lambda r:r[1]) if prv else None)
        if r is None:
            info['where']='in_speech'; return snap(src,t),info
        room=r[1]-r[0]
        lo=r[0]+min(need+0.02,room*0.6)
        t2=min(max(t,lo),r[1]-0.02) if inside else lo
        info['room']=round(r[1]-t2,3); info['sil_start']=r[0]
        return round(t2,3),info
    if inside:
        r=inside[0]
        t2=t if r[1]-t<=0.15 else r[1]-0.06
        return round(max(r[0],t2),3),info
    prv=[r for r in runs if t-back-0.15<=r[1]<=t+0.05]
    nxt=[r for r in runs if t-0.02<=r[0]<=t+fwd]
    r=max(prv,key=lambda r:r[1]) if prv else (min(nxt,key=lambda r:r[1]) if nxt else None)
    if r is None:
        info['where']='in_speech'; return snap(src,t),info
    return round(max(r[0],r[1]-0.05),3),info


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
FIX=[(a,b) for a,b in JOB.get('fix',[])]+[(r'\bBesos\b','berços'),(r'\bserbo\b','sebo'),(r'\bsó da cálcica\b','soda cáustica'),
     (r'\bquem daí de vocês\b','quem aí de vocês'),(r'\bda granel\b','da Granel'),
     (r'\bgranel\b','Granel'),(r'\bCoca-Cola\b','Coca-Cola'),(r'\bpo r\b','por'),
     (r'\bteraprima\b','matéria-prima'),(r'\bvódica\b','vodka'),
     (r'\bfaço parte\b','faço parte'),(r'Porto, gente','porto, gente'),
     (r'dentro do Porto','dentro do porto'),(r'\bvai só da cálcica\b','vai soda cáustica'),
     (r'\bsó da cálcica\b','soda cáustica'),(r'\bEla não tem lá um\b','Ela não tem lá um')]

# words that get the big/impact treatment
EMPH = set(JOB.get('emph','').split()) | set('''80% mundo portuário portuário. risco risco. altíssimo gasolina moeda moeda?
banho banho. sabonete sabonete? sebo sebo, cáustica cáustica, coca-cola pigmento vermelha
navios navios. 42 anos enorme granel granel. econômica econômica. oportunidade oportunidade.
incidente segurança segurança? líquida líquida.'''.split())

def norm(w): return re.sub(r'[^0-9a-záàâãéêíóôõúüç%\-]','',w.lower())


MINB=float(os.environ.get('MIN_BLOCK','0.45'))   # s: abaixo disso a legenda pisca
MAXCPS=float(os.environ.get('MAX_CPS','20'))     # caracteres por segundo confortaveis
MAXMERGE=int(os.environ.get('MAX_MERGE_CHARS','30'))  # ate aqui ainda cabe em duas linhas

def _rebuild(o):
    ws=o['t'].split()
    o['w']=ws; o['em']=[norm(w) in EMPH for w in ws]; o['any']=any(o['em'])
    return o

def ritmo(out,total):
    """Nenhuma legenda pisca, corre ou some.

    Um bloco de uma palavra com 0,15 s chega a 60 caracteres por segundo e na
    tela vira flash ilegivel. A ordem de tentativa importa: esticar para dentro
    do silencio seguinte e de graca; pedir tempo emprestado ao vizinho so custa
    se ele tambem estiver apertado; fundir e o ultimo recurso, porque engorda a
    linha. Descartar o bloco nunca e opcao — sumir com a fala do entrevistado e
    pior que uma legenda apertada, e some sem deixar rastro no relatorio.
    """
    def alvo(o): return max(MINB,len(o['t'])/MAXCPS)
    for _ in range(3):
        for i in range(len(out)-1,-1,-1):
            o=out[i]
            if o['e']-o['s'] >= alvo(o)-1e-3: continue
            teto=min(out[i+1]['s'] if i+1<len(out) else total,o['sg_end'])
            o['e']=min(teto,o['s']+alvo(o))
            if o['e']-o['s'] >= alvo(o)-1e-3: continue
            if i+1<len(out) and out[i+1]['sg']==o['sg']:
                p=out[i+1]; sobra=(p['e']-p['s'])-alvo(p)
                if sobra>0.02:
                    d=min(sobra,alvo(o)-(o['e']-o['s'])); p['s']+=d; o['e']+=d
            if i>0 and out[i-1]['sg']==o['sg'] and o['e']-o['s'] < alvo(o)-1e-3:
                a=out[i-1]; sobra=(a['e']-a['s'])-alvo(a)
                if sobra>0.02:
                    d=min(sobra,alvo(o)-(o['e']-o['s'])); a['e']-=d; o['s']-=d
            if o['e']-o['s'] >= alvo(o)-1e-3: continue
            if i>0 and out[i-1]['sg']==o['sg'] and len(out[i-1]['t']+' '+o['t'])<=MAXMERGE:
                a=out[i-1]; a['t']=a['t']+' '+o['t']; a['e']=max(a['e'],o['e'])
                _rebuild(a); out.pop(i); continue
            if i+1<len(out) and out[i+1]['sg']==o['sg'] and len(o['t']+' '+out[i+1]['t'])<=MAXMERGE:
                p=out[i+1]; o['t']=o['t']+' '+p['t']; o['e']=max(o['e'],p['e'])
                _rebuild(o); out.pop(i+1)
    # ninguem invade o vizinho, e ninguem e jogado fora
    limpo=[]
    for i,o in enumerate(out):
        teto=min(out[i+1]['s'] if i+1<len(out) else total,o['sg_end'])
        o['e']=min(o['e'],teto)
        if o['e']-o['s'] < 0.10:
            if limpo and limpo[-1]['sg']==o['sg']:
                limpo[-1]['t']+=' '+o['t']; limpo[-1]['e']=max(limpo[-1]['e'],o['e'])
                _rebuild(limpo[-1])
                continue
            o['e']=min(o['sg_end'],o['s']+0.10)
        limpo.append(o)
    return limpo

def build(name):
    c=CLIPS[name]; mi=c['master_in']
    # local groups
    g=[]
    for s,e,t in GROUPS:
        ls,le=s-mi,e-mi
        if le<=0: continue
        g.append([ls,le,t])
    # keep-map: source time -> final time
    K=c['keeps']; keeps=[]; audit=[]; fade_last=None
    exact=bool(c.get('exact_edges',False))   # opt-out: first start / last end exactly as authored
    for i,(a,b) in enumerate(K):
        first=(i==0); last=(i==len(K)-1)
        xb=set(c.get('exact_bounds',[]))          # e.g. ["3:start"]: keep this one exactly as authored
        a2,ia=(a,dict(src_t=a,where='exact')) if ((exact and first) or f'{i}:start' in xb) else place(c['src'],a,'start')
        b2,ib=(b,dict(src_t=b,where='exact')) if ((exact and last) or f'{i}:end' in xb) else place(c['src'],b,'end',last=last)
        keeps.append((a2,b2))
        audit.append(dict(seg=i,edge='start',to=a2,**ia)); audit.append(dict(seg=i,edge='end',to=b2,**ib))
        if last and ib.get('sil_start') is not None:
            fade_last=round(max(0.03,min(0.12,b2-ib['sil_start']-0.005)),3)
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
        for si,(a,b,off) in enumerate(segs):
            s2,e2=max(ls,a),min(le,b)
            if e2-s2<=0.12: continue
            txt=t
            for pat,rep in FIX: txt=re.sub(pat,rep,txt,flags=re.I)
            # Only caption what is actually heard. A cue clipped by a keep
            # boundary used to ship its FULL text as long as 0.12 s of it
            # survived, so the screen showed a whole sentence the viewer never
            # hears -- the audio was trimmed away but the caption stayed. When
            # the kept part is a fraction of the cue, keep the matching fraction
            # of the words; when nothing legible survives, drop the atom.
            span=max(1e-6,le-ls); frac=(e2-s2)/span
            if frac<0.85:
                ws=txt.split()
                i0=int(len(ws)*((s2-ls)/span)); i1=int(round(len(ws)*((e2-ls)/span)))
                ws=ws[i0:max(i0+1,i1)] if i1>i0 else []
                txt=' '.join(ws)
                if not txt.strip(): continue
            atoms.append([off+(s2-a),off+(e2-a),txt.strip(),si])
    atoms.sort()
    # split any atom whose whole SRT cue already exceeds the caption limit —
    # otherwise a long, unfragmented whisper segment ships as one on-screen
    # wall of text instead of the intended short auto-wrapped captions.
    _split=[]
    for a0,a1,txt,sg in atoms:
        if len(txt)<=18:
            _split.append([a0,a1,txt,sg]); continue
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
            _split.append([t,c_end,chunk,sg]); t=c_end
    atoms=_split
    # merge into <=18 char captions
    caps=[]
    for a in atoms:
        if caps:
            p=caps[-1]
            cand=(p[2]+' '+a[2]).replace('  ',' ').strip()
            cand=re.sub(r'\s+([,.?!])',r'\1',cand)
            if len(cand)<=18 and a[0]-p[1]<0.30 and (a[1]-p[0])<2.2 and a[3]==p[3]:
                p[1]=a[1]; p[2]=cand; continue
        caps.append([a[0],a[1],a[2],a[3]])
    # second pass: absorb tiny orphan captions
    i=1
    while i<len(caps):
        if caps[i][3]==caps[i-1][3] and len(caps[i][2])<=4 and caps[i-1][1]-caps[i-1][0]<2.6 and len((caps[i-1][2]+' '+caps[i][2]))<=18:
            caps[i-1][1]=caps[i][1]; caps[i-1][2]=(caps[i-1][2]+' '+caps[i][2]).strip(); caps.pop(i); continue
        i+=1
    # tidy + emphasis
    out=[]
    segend=[off+(b-a) for a,b,off in segs]
    for s,e,t,sg in caps:
        t=re.sub(r'\s+',' ',t).strip().strip('-').strip()
        t=re.sub(r'\.\.\.$','...',t)
        if not t: continue
        if e-s<0.30: e=s+0.30
        for pat,rep in FIX: t=re.sub(pat,rep,t)
        ws=t.split(); flags=[norm(w) in EMPH for w in ws]
        out.append(dict(s=round(s,3),e=round(e,3),t=' '.join(ws),w=ws,em=flags,any=any(flags),sg=sg,sg_end=segend[sg]))
    # de-overlap
    for i in range(len(out)-1):
        if out[i]['e']>out[i+1]['s']: out[i]['e']=out[i+1]['s']
    # Nunca descartar bloco por ser curto: o codigo antigo apagava em silencio
    # legendas que o de-overlap tinha espremido, sumindo com uma frase falada
    # sem deixar rastro. O passe de ritmo estica, empresta tempo ou funde.
    out=[o for o in out if o['e']<=total+0.05]
    out=ritmo(out,total)
    for o in out: o.pop('sg',None); o.pop('sg_end',None)
    result=dict(name=name, filename=c.get('filename',name), src=c['src'], keeps=keeps, total=round(total,3),
                headline=c['headline'], cropx=c['cropx'], cover_t=c['cover_t'],
                cropx_timeline=c.get('cropx_timeline',[]),
                mix={**JOB.get('mix',{}), **c.get('mix',{})},
                music=c.get('music'), impact_pulses=c.get('impact_pulses',[]),
                long_moves=c.get('long_moves',[]),
                click_times=c.get('click_times',[]), caps=out,
                cut_audit=audit, fade_out=c.get('fade_out',fade_last if fade_last is not None else 0.06))
    # repassa qualquer outro campo do job (logo, filename novo, ...) sem
    # descartar em silencio config que esta funcao nao conhece
    for key,val in c.items():
        if key not in result: result[key]=val
    return result

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
                t=c['s']+1.0   # +1s cover at the head of the delivered file
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
