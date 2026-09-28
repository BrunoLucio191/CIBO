# -*- coding: utf-8 -*-
import os
import json,sys,subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter
B=os.environ.get('WORK','.'); W,H=1080,1920
FONT=os.environ['FONT']
LOGO=os.environ.get('LOGO','')
BLUE=(79,149,255)

def grab(src,t):
    raw=subprocess.run(f'ffmpeg -v error -ss {t} -i "{src}" -frames:v 1 -f rawvideo -pix_fmt rgb24 -',
                       shell=True,capture_output=True).stdout
    return Image.frombytes('RGB',(W,H),raw[:W*H*3])

def fit(txt,maxw,start=104):
    s=start
    while s>50:
        ft=ImageFont.truetype(FONT,s)
        if max(ft.getbbox(l)[2]-ft.getbbox(l)[0] for l in txt.split('\n'))<=maxw: return ft,s
        s-=3
    return ImageFont.truetype(FONT,s),s

def grab_from(cf):
    """Cover still from ANY moment of the episode, not only from inside the cut:
    the flattering frontal smile is often in the guest's introduction, while the cut
    itself only shows her in profile. cf={'src': video, 't': s, 'x0': crop x (px of
    the 1920 source)}; crops the same 608x1080 window the reels use, scales to 1080x1920."""
    raw=subprocess.run(['ffmpeg','-v','error','-ss',str(cf['t']),'-i',cf['src'],'-frames:v','1',
                        '-vf',f"crop=608:1080:{int(cf.get('x0',656))}:0,scale={W}:{H}:flags=lanczos",
                        '-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True).stdout
    return Image.frombytes('RGB',(W,H),raw[:W*H*3])

def retouch(im,amount=0.35):
    """Subtle, natural: edge-preserving skin smoothing blended at `amount`, a touch of light."""
    import numpy as np, cv2
    a=np.asarray(im).copy()
    sm=cv2.bilateralFilter(a,9,40,9)
    a=cv2.addWeighted(a,1-amount,sm,amount,0)
    a=np.clip(a.astype(np.float32)*1.04+3,0,255).astype(np.uint8)
    return Image.fromarray(a)

def build(c,src,out):
    cf=c.get('cover_from')
    im=(grab_from(cf) if cf else grab(src,c['cover_t'])).convert('RGB')
    if c.get('cover_retouch',bool(cf)): im=retouch(im,float(c.get('cover_retouch_amount',0.35)))
    # vignette / bottom scrim
    sc=Image.new('L',(1,H))
    for y in range(H):
        v=0
        if y>H*0.42: v=int(235*min(1,((y-H*0.42)/(H*0.42))**1.25))
        sc.putpixel((0,y),v)
    scrim=sc.resize((W,H))
    dark=Image.new('RGB',(W,H),(6,10,20))
    im=Image.composite(dark,im,scrim)
    d=ImageDraw.Draw(im)
    lines=c['headline'].split('\n')
    ft,s=fit(c['headline'],W-150,110)
    lh=int(s*1.16); total=lh*len(lines)
    y=int(H*0.735)-total//2
    for i,l in enumerate(lines):
        bb=ft.getbbox(l); w=bb[2]-bb[0]; x=(W-w)//2-bb[0]
        yy=y+i*lh
        sh=Image.new('RGBA',(W,lh+60),(0,0,0,0))
        ImageDraw.Draw(sh).text((x,10-bb[1]),l,font=ft,fill=(0,0,0,200))
        sh=sh.filter(ImageFilter.GaussianBlur(14))
        im.paste(Image.alpha_composite(im.crop((0,yy-10,W,yy+lh+50)).convert('RGBA'),sh).convert('RGB'),(0,yy-10))
        d.text((x,yy-bb[1]),l,font=ft,fill=(255,255,255))
    # blue accent bar
    bw=int(W*0.16)
    d.rounded_rectangle([(W-bw)//2,y-58,(W+bw)//2,y-46],6,fill=BLUE)
    # logo
    try:
        lg=Image.open(LOGO).convert('RGBA')
        px=lg.load()
        for yy2 in range(lg.height):
            for xx2 in range(lg.width):
                r,g,b,a=px[xx2,yy2]
                if a>10 and max(r,g,b)-min(r,g,b)<45: px[xx2,yy2]=(255,255,255,a)
        lw=150; lg=lg.resize((lw,int(lg.height*lw/lg.width)),Image.LANCZOS)
        im.paste(lg,((W-lw)//2,90),lg)
    except Exception as e: print('logo skip',e)
    im.save(out)

if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json'))); k=sys.argv[1]
    build(P[k],f'{B}/A_{k}.mp4',f'{B}/capa_{k}.png'); print('ok')
