# -*- coding: utf-8 -*-
import os
import json,sys,os,math,subprocess
import numpy as np
from PIL import Image, ImageFilter

B=os.environ.get('WORK','.'); SRCDIR=os.environ.get('SRCDIR','.')
FPS=30; W,H=1080,1920
INTRO=0.90; Z0=1.26; BLUR0=18.0

def sh(cmd):
    r=subprocess.run(cmd,shell=True,capture_output=True,text=True)
    if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
    return r.stdout

ZOOM=float(os.environ.get('ZOOM_AMT','0.055'))   # 0 disables
def ease_quad(p): return 2*p*p if p<0.5 else 1-((-2*p+2)**2)/2

def passA(c,out):
    """Cut+crop+ken-burns. The zoom used to be done with ffmpeg's `zoompan`, which has a
    well-known bug: fed a continuously-changing video (not a still), it silently duplicates
    every other output frame, producing a regular judder that reads as shake. Fixed by doing
    the animated crop/zoom frame-by-frame in Python (PIL), the same technique make_intro()
    already used successfully - ffmpeg only decodes/encodes, no zoompan involved."""
    keeps=c['keeps']; n=len(keeps)
    # oversample relative to the FINAL output size (not the native crop size) so the zoom
    # only ever crops+lightly-downscales from an already-adequate source instead of upscaling.
    OS=int(H*(1+ZOOM+0.02)); OSW=int(W*(1+ZOOM+0.02))//2*2
    cw=608; x=int((1920-cw)*c['cropx']); x=max(0,min(1920-cw,x))
    src=f'{SRCDIR}/{c["src"]}'
    base=1+ZOOM+0.02
    fsz=OSW*OS*3

    afc=[]
    for i,(a,b) in enumerate(keeps):
        afc.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d=0.035,afade=t=out:st={round(b-a-0.055,3)}:d=0.055[a{i}]")
    afc.append(''.join(f"[a{i}]" for i in range(n))+f"concat=n={n}:v=0:a=1[ac]")
    afc.append("[ac]aresample=48000,asetpts=N/SR/TB[ao]")
    audio_out=out+'.audio.m4a'
    sh(f'ffmpeg -y -v error -i "{src}" -filter_complex "{";".join(afc)}" -map "[ao]" '
       f'-c:a aac -b:a 192k "{audio_out}"')

    video_out=out+'.video.mp4'
    enc=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','ultrafast',
        '-crf','14','-pix_fmt','yuv420p',video_out],stdin=subprocess.PIPE)
    for i,(a,b) in enumerate(keeps):
        zin=(i%2==0)                      # alternate push-in / pull-out per beat
        zA,zB=(1.0,1.0+ZOOM) if zin else (1.0+ZOOM,1.0)
        nframes=max(1,round((b-a)*FPS))
        dec=subprocess.Popen(['ffmpeg','-v','error','-i',src,'-filter_complex',
            f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,crop={cw}:1080:{x}:0,'
            f'scale={OSW}:{OS}:flags=lanczos,format=rgb24[v]','-map','[v]','-f','rawvideo','-'],
            stdout=subprocess.PIPE)
        for k in range(nframes):
            buf=dec.stdout.read(fsz)
            if len(buf)<fsz: break
            im=Image.frombytes('RGB',(OSW,OS),buf)
            if ZOOM>0:
                p=k/max(1,nframes-1)
                e=ease_quad(p)
                z=base/(zA+(zB-zA)*e)
                cw2,ch2=OSW/z,OS/z
                x0=(OSW-cw2)/2; y0=(OS-ch2)/2
                im=im.crop((x0,y0,x0+cw2,y0+ch2)).resize((W,H),Image.LANCZOS)
            else:
                im=im.resize((W,H),Image.LANCZOS)
            enc.stdin.write(im.tobytes())
        dec.stdout.close(); dec.wait()
    enc.stdin.close(); enc.wait()
    sh(f'ffmpeg -y -v error -i "{video_out}" -i "{audio_out}" -map 0:v -map 1:a '
       f'-c:v copy -c:a copy -shortest "{out}"')
    os.remove(video_out); os.remove(audio_out)

def ease_io(p): return 4*p*p*p if p<0.5 else 1-((-2*p+2)**3)/2

def make_intro(passa,out):
    n=int(round(INTRO*FPS))
    raw=subprocess.run(f'ffmpeg -v error -i "{passa}" -frames:v {n} -f rawvideo -pix_fmt rgb24 -',
                       shell=True,capture_output=True).stdout
    fs=W*H*3
    p=subprocess.Popen(['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
        '-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','veryfast',
        '-crf','16','-pix_fmt','yuv420p',out],stdin=subprocess.PIPE)
    for i in range(n):
        im=Image.frombytes('RGB',(W,H),raw[i*fs:(i+1)*fs])
        e=ease_io(i/(n-1))
        z=Z0-(Z0-1.0)*e
        bl=BLUR0*(1-e)**1.4
        cw,ch=int(W/z),int(H/z)
        im=im.crop(((W-cw)//2,(H-ch)//2,(W-cw)//2+cw,(H-ch)//2+ch)).resize((W,H),Image.LANCZOS)
        if bl>0.3: im=im.filter(ImageFilter.GaussianBlur(bl))
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()

def final(c,passa,intro,out,cover=None,preset='veryfast',crf=21,extra=''):
    """One single encode: cover + burn + captions + click + music mix -> deliverable."""
    k=c['name']
    fb=os.environ['FILMBURN']; cr=f'{B}/caps_{k}_rgb.mp4'; ca=f'{B}/caps_{k}_a.mp4'
    clk=f'{B}/clicks_{k}.wav'
    music=c.get('music'); mix=c.get('mix',{})
    ins=(f'-i "{passa}" -i "{intro}" -i "{fb}" -i "{cr}" -i "{ca}" -i "{clk}"')
    if music: ins+=f' -stream_loop -1 -i "{music}"'
    f=(f"[0:v]trim=start={INTRO},setpts=PTS-STARTPTS[main];"
       f"[1:v][main]concat=n=2:v=1:a=0[vv];"
       f"[2:v]tpad=stop_mode=add:stop_duration=120:color=black,fps={FPS},format=gbrp[fbp];"
       f"[vv]format=gbrp[vvg];"
       f"[vvg][fbp]blend=all_mode=screen:shortest=1,format=yuv420p[vb];"
       f"[3:v]format=yuva420p[c3];[c3][4:v]alphamerge[capa];"
       f"[vb][capa]overlay=x=0:y=810:format=auto:eof_action=pass,setsar=1[body];"
       f"[0:a][5:a]amix=inputs=2:duration=first:normalize=0[voice]")
    if music:
        music_db=float(mix.get('music_db',-26))
        music_offset=max(0.0,float(mix.get('music_offset',0)))
        music_fade_out=max(0.0,float(c['total'])-0.8)
        duck_threshold=float(mix.get('duck_threshold',0.08))
        duck_ratio=float(mix.get('duck_ratio',6))
        f+=(f";[6:a]atrim=start={music_offset:.3f},asetpts=PTS-STARTPTS,"
            f"volume={music_db:g}dB,afade=t=in:d=0.8,afade=t=out:st={music_fade_out:.3f}:d=0.8[music];"
            f"[music][voice]sidechaincompress=threshold={duck_threshold:.3f}:ratio={duck_ratio:g}:attack=12:release=420[duck];"
            f"[voice][duck]amix=inputs=2:duration=first:normalize=0[abody]")
    else:
        f+=";[voice]anull[abody]"
    if cover:
        cd=1.0/FPS  # Instagram only needs one frame to grab a thumbnail from
        cover_idx=7 if music else 6
        ins+=f' -loop 1 -t {cd} -i "{cover}"'
        f+=(f";[{cover_idx}:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1[cv];"
            f"[cv][body]concat=n=2:v=1:a=0[vfin];"
            f"anullsrc=r=48000:cl=stereo,atrim=0:{cd},asetpts=N/SR/TB[sil];"
            f"[sil][abody]concat=n=2:v=0:a=1[afin]")
    else:
        f+=";[body]null[vfin];[abody]anull[afin]"
    sh(f'ffmpeg -y -v error {ins} -filter_complex "{f}" -map "[vfin]" -map "[afin]" '
       f'-c:v libx264 -preset {preset} -crf {crf} -pix_fmt yuv420p -c:a aac -b:a 160k '
       f'{extra} -movflags +faststart "{out}"')

if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json'))); k=sys.argv[1]; c=P[k]
    passA(c,f'{B}/A_{k}.mp4'); print('passA ok')
    make_intro(f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4'); print('intro ok')
    final(c,f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4',f'{B}/{k}_vertical.mp4'); print('final ok')
