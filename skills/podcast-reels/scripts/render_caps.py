# -*- coding: utf-8 -*-
import os
import json, math, subprocess, sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from easing import entrance, ease_out_back

import os
FONT=os.environ['FONT']
W=1080; BAND_H=420; BAND_Y=810     # band top in the 1920-tall frame
CY=1020-BAND_Y                      # caption center inside band
FPS=30
BASE=74; EMPH=100; LINE_GAP=1.12
MAXW=W-150

def f(sz):
    ft=ImageFont.truetype(FONT,sz)
    try: ft.set_variation_by_name(os.environ.get('FONT_WEIGHT','Bold'))
    except Exception: pass
    return ft

def metrics(sz):
    ft=f(sz); a,d=ft.getmetrics(); return ft,a,d

def adv(word,sz):
    return f(sz).getlength(word)

def layout(words,flags):
    """[[ (word,size,flag) ]] lines that fit MAXW, plus scale"""
    sc=1.0
    for _ in range(16):
        base=int(BASE*sc); emp=int(EMPH*sc)
        sizes=[emp if fl else base for fl in flags]
        sp=base*0.30
        tot=sum(adv(w,s) for w,s in zip(words,sizes))+sp*(len(words)-1)
        if tot<=MAXW: return [list(zip(words,sizes,flags))],sc
        best=None
        for k in range(1,len(words)):
            wa=sum(adv(x,s) for x,s in zip(words[:k],sizes[:k]))+sp*(k-1)
            wb=sum(adv(x,s) for x,s in zip(words[k:],sizes[k:]))+sp*(len(words)-k-1)
            m=max(wa,wb)
            if best is None or m<best[0]: best=(m,k)
        if best and best[0]<=MAXW:
            k=best[1]
            return [list(zip(words[:k],sizes[:k],flags[:k])),
                    list(zip(words[k:],sizes[k:],flags[k:]))],sc
        sc*=0.94
    return [list(zip(words,[int(BASE*sc)]*len(words),flags))],sc

def draw_word(word,sz):
    """RGBA tile drawn from a fixed origin so the BASELINE is known exactly."""
    ft,asc,desc=metrics(sz)
    pad=int(sz*0.60)
    tw=int(ft.getlength(word))+pad*2
    th=asc+desc+pad*2
    sh=Image.new('RGBA',(tw,th),(0,0,0,0))
    ImageDraw.Draw(sh).text((pad,pad+int(sz*0.05)),word,font=ft,fill=(0,0,0,195))
    sh=sh.filter(ImageFilter.GaussianBlur(sz*0.13))
    tl=Image.new('RGBA',(tw,th),(0,0,0,0))
    ImageDraw.Draw(tl).text((pad,pad),word,font=ft,fill=(255,255,255,255))
    out=Image.alpha_composite(sh,tl)
    return out,pad,pad+asc,ft.getlength(word),asc,desc

def build_caption(words,flags):
    lines,sc=layout(words,flags)
    base=BASE*sc; sp=base*0.30
    L=[]
    for ln in lines:
        ws=[(w,s,fl)+draw_word(w,s) for w,s,fl in ln]
        L.append(ws)
    # vertical block: baseline per line
    asc=[max(x[7] for x in ws) for ws in L]
    des=[max(x[8] for x in ws) for ws in L]
    gap=int(max(max(s for _,s,_,_,_,_,_,_,_ in ws) for ws in L)*0.16)
    total=sum(a+d for a,d in zip(asc,des))+gap*(len(L)-1)
    top=CY-total/2.0
    items=[]; y=top
    for i,ws in enumerate(L):
        bl=y+asc[i]
        width=sum(x[6] for x in ws)+sp*(len(ws)-1)
        x=(W-width)/2.0
        for (w,s,fl,tile,ox,oy,aw,a2,d2) in ws:
            capH=s*0.70
            items.append(dict(tile=tile,
                              px=x, bl=bl,
                              ax=ox+aw/2.0, ay=oy-capH/2.0,
                              cx=x+aw/2.0,  cy=bl-capH/2.0, fl=fl))
            x+=aw+sp
        y=bl+des[i]+gap
    return items

def eob(p,s=1.55): return 1+(s+1)*(p-1)**3+s*(p-1)**2

def paste(canvas,tile,cx,cy,ax,ay,scale,alpha,dx=0.0,dy=0.0):
    if alpha<=0.004: return
    w=max(1,int(round(tile.width*scale))); h=max(1,int(round(tile.height*scale)))
    t=tile.resize((w,h),Image.LANCZOS) if abs(scale-1)>1e-3 else tile.copy()
    if alpha<0.999:
        a=t.getchannel('A').point(lambda v:int(v*alpha)); t.putalpha(a)
    x=int(round(cx-ax*scale+dx)); y=int(round(cy-ay*scale+dy))
    canvas.alpha_composite(t,(x,y))

def render(clip,outdir):
    caps=clip['caps']; total=clip['total']
    for c in caps: c['items']=build_caption(c['w'],c['em'])
    nfr=int(math.ceil(total*FPS))+2
    p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgba',
        '-s','%dx%d'%(W,BAND_H),'-r',str(FPS),'-i','-',
        '-filter_complex','[0:v]split[c][a];[c]format=yuv420p[cv];[a]alphaextract,format=gray[av]',
        '-map','[cv]','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p',outdir+'_rgb.mp4',
        '-map','[av]','-c:v','libx264','-preset','veryfast','-crf','16','-pix_fmt','yuv420p',outdir+'_a.mp4'],
        stdin=subprocess.PIPE)
    blank=Image.new('RGBA',(W,BAND_H),(0,0,0,0))
    for i in range(nfr):
        t=i/FPS
        act=[c for c in caps if c['s']-0.02<=t<c['e']]
        if not act:
            p.stdin.write(blank.tobytes()); continue
        cv=Image.new('RGBA',(W,BAND_H),(0,0,0,0))
        for c in act:
            dt=t-c['s']
            pb=min(1.0,max(0.0,dt/0.12))
            # whole caption block: slides in from `slide_dir` (default up) while fading in,
            # decelerating into place — see lettering-motion/references/animation-catalog.md
            ddx,ddy,ab=entrance(pb,direction=c.get('slide_dir','up'),distance=c.get('slide_px',34))
            for it in c['items']:
                if it['fl']:
                    pe=min(1.0,max(0.0,(dt-0.03)/0.24))
                    sc=max(0.6,1.26-0.26*eob(pe))
                    al=min(1.0,max(0.0,(dt-0.03)/0.09))
                    paste(cv,it['tile'],it['cx'],it['cy'],it['ax'],it['ay'],sc,al*ab,ddx,ddy)
                else:
                    paste(cv,it['tile'],it['cx'],it['cy'],it['ax'],it['ay'],1.0,ab,ddx,ddy)
        p.stdin.write(cv.tobytes())
    p.stdin.close(); p.wait()
    return nfr

if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json')))
    k=sys.argv[1]
    n=render(P[k],os.path.join(B,'caps_%s'%k))
    print(k,'frames',n)
