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

def bolden(ft):
    try: ft.set_variation_by_name(os.environ.get('FONT_WEIGHT','Bold'))
    except Exception: pass
    return ft

def fit(txt,maxw,start=104):
    s=start
    while s>50:
        ft=bolden(ImageFont.truetype(FONT,s))
        if max(ft.getbbox(l)[2]-ft.getbbox(l)[0] for l in txt.split('\n'))<=maxw: return ft,s
        s-=3
    return bolden(ImageFont.truetype(FONT,s)),s

def build(c,src,out):
    im=grab(src,c['cover_t']).convert('RGB')
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
