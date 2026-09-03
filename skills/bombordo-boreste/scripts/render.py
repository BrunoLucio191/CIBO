# -*- coding: utf-8 -*-
import os
import json,sys,os,math,subprocess
import numpy as np
from PIL import Image, ImageFilter

B=os.environ.get('WORK','.'); SRCDIR=os.environ.get('SRCDIR','.')
FPS=30; W,H=1080,1920
INTRO=0.90; Z0=1.26; BLUR0=18.0
OUTRO_BURN=0.80; OUTRO_FADE=0.42; OUTRO_BLACK=0.18

def sh(cmd):
    r=subprocess.run(cmd,shell=True,capture_output=True,text=True)
    if r.returncode: print(r.stderr[-3000:]); raise SystemExit(1)
    return r.stdout

PULSE_AMT=float(os.environ.get('PULSE_AMT','0.050'))
PULSE_DUR=float(os.environ.get('PULSE_DUR','1.00'))

def impact_motion(c):
    """Time-coded movement on the final timeline; edits never reset the camera."""
    events=[]
    for event in c.get('impact_pulses',[]):
        if isinstance(event,dict):
            events.append((float(event['t']),float(event.get('amount',PULSE_AMT)),
                           float(event.get('duration',PULSE_DUR))))
        else:
            events.append((float(event),PULSE_AMT,PULSE_DUR))
    for event in c.get('long_moves',[]):
        events.append((float(event['t']),float(event.get('amount',0.045)),
                       float(event.get('duration',1.6))))
    if not events:
        return f'[vc]scale={W}:{H}:flags=lanczos,format=yuv420p[vo]'
    terms=[]
    for t,amount,duration in events:
        start=max(0.0,t-0.08); end=start+duration
        # sin(PI*x) starts and ends at rest, giving a real ease-in/ease-out pulse.
        terms.append(
            f"if(between(on/{FPS},{start:.3f},{end:.3f}),"
            f"{amount:.3f}*sin(PI*(on/{FPS}-{start:.3f})/{duration:.3f}),0)"
        )
    z='1+'+'+'.join(terms)
    return (f"[vc]scale=1140:2028:flags=lanczos,"
            f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d=1:s={W}x{H}:fps={FPS},format=yuv420p[vo]")

def passA(c,out):
    keeps=c['keeps']; n=len(keeps); fc=[]
    cw=608
    timeline=sorted((float(t),float(x)) for t,x in c.get('cropx_timeline',[]))
    def crop_expr(a,b):
        current=float(c['cropx']); changes=[]
        for t,x in timeline:
            if t <= a+1e-6: current=x
            elif t < b-1e-6: changes.append((t-a,x))
        vals=[current]+[x for _,x in changes]
        expr=f'{vals[-1]:.5f}'
        for j in range(len(changes)-1,-1,-1):
            boundary=changes[j][0]
            expr=f'if(lt(t,{boundary:.5f}),{vals[j]:.5f},{expr})'
        return f'(iw-{cw})*({expr})'
    for i,(a,b) in enumerate(keeps):
        # snap to exact frame boundaries: a fractional-second trim start forces the
        # later `fps={FPS}` filter to duplicate frames to realign, producing a regular
        # every-other-frame stutter that reads as a shake/vibration.
        a=round(a*FPS)/FPS; b=round(b*FPS)/FPS
        d=max(0.2,b-a); N=max(1,int(round(d*FPS))-1)
        x=crop_expr(a,b)
        vf=(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,"
            f"crop={cw}:1080:x='{x}':y=0,scale={W}:{H}:flags=lanczos,fps={FPS}")
        fc.append(vf+f"[v{i}]")
        fade_out=0.120 if i==n-1 else 0.020
        fc.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.012,afade=t=out:st={round(b-a-fade_out,3)}:d={fade_out:.3f}[a{i}]")
    fc.append(''.join(f"[v{i}][a{i}]" for i in range(n))+f"concat=n={n}:v=1:a=1[vc][ac]")
    fc.append(impact_motion(c))
    fc.append("[ac]aresample=48000,asetpts=N/SR/TB[ao]")
    f=';'.join(fc)
    sh(f'ffmpeg -y -v error -i "{SRCDIR}/{c["src"]}" -filter_complex "{f}" -map "[vo]" -map "[ao]" '
       f'-c:v libx264 -preset ultrafast -crf 14 -c:a aac -b:a 192k "{out}"')

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
    """One single encode: cover + burn + captions + click mix -> deliverable."""
    k=c['name']
    fb=os.environ['FILMBURN']; cr=f'{B}/caps_{k}_rgb.mp4'; ca=f'{B}/caps_{k}_a.mp4'
    clk=f'{B}/clicks_{k}.wav'
    ins=(f'-i "{passa}" -i "{intro}" -i "{fb}" -i "{cr}" -i "{ca}" -i "{clk}"')
    music=c.get('music')
    mix=c.get('mix',{})
    burn_d=1.366667
    burn_gap=max(0.0,float(c['total'])-burn_d-OUTRO_BURN)
    burn_delay=max(0,int(round((float(c['total'])-OUTRO_BURN)*1000)))
    fade_start=max(0.0,float(c['total'])-OUTRO_FADE)
    if music:
        ins+=f' -stream_loop -1 -i "{music}"'
    f=(f"[0:v]trim=start={INTRO},setpts=PTS-STARTPTS[main];"
       f"[1:v][main]concat=n=2:v=1:a=0[vv];"
       f"[2:v]fps={FPS},setpts=PTS-STARTPTS,setsar=1,format=gbrp,split=2[fbi0][fbo0];"
       f"[fbi0]trim=duration={burn_d:.6f},setpts=PTS-STARTPTS[fbi];"
       f"[fbo0]trim=duration={OUTRO_BURN:.6f},setpts=PTS-STARTPTS[fbo];"
       f"color=c=black:s={W}x{H}:r={FPS}:d={burn_gap:.6f},setsar=1,format=gbrp[gap];"
       f"[fbi][gap][fbo]concat=n=3:v=1:a=0[fbp];"
       f"[vv]setsar=1,format=gbrp[vvg];"
       f"[vvg][fbp]blend=all_mode=screen:shortest=1,format=yuv420p[vb];"
       f"[3:v]format=yuva420p[c3];[c3][4:v]alphamerge[capa];"
       f"[vb][capa]overlay=x=0:y=810:format=auto:eof_action=pass,setsar=1,"
       f"fade=t=out:st={fade_start:.6f}:d={OUTRO_FADE:.6f},format=yuv420p[bodyfade];"
       f"color=c=black:s={W}x{H}:r={FPS}:d={OUTRO_BLACK:.6f},setsar=1,format=yuv420p[endblack];"
       f"[bodyfade][endblack]concat=n=2:v=1:a=0[body];"
       f"[0:a][5:a]amix=inputs=2:duration=first:normalize=0[voice]")
    if music:
        music_db=float(mix.get('music_db',-21))
        duck_threshold=float(mix.get('duck_threshold',0.08))
        duck_ratio=float(mix.get('duck_ratio',5))
        f+=(f";[6:a]volume={music_db:g}dB,afade=t=in:d=0.8[music];"
            f"[music][voice]sidechaincompress=threshold={duck_threshold:.3f}:ratio={duck_ratio:g}:attack=12:release=420[duck];"
            f"[voice][duck]amix=inputs=2:duration=first:normalize=0[abase]")
    else:
        f+=';[voice]anull[abase]'
    burn_db=float(mix.get('outro_burn_db',-6))
    limiter=float(mix.get('limiter',0.85))
    limiter_level='true' if bool(mix.get('limiter_level',False)) else 'false'
    fb_has_audio='audio' in subprocess.run(
        ['ffprobe','-v','error','-select_streams','a','-show_entries','stream=codec_type',
         '-of','csv=p=0',fb],capture_output=True,text=True).stdout
    if fb_has_audio:
        f+=(f";[2:a]atrim=duration={OUTRO_BURN:.6f},asetpts=PTS-STARTPTS,"
            f"volume={burn_db:g}dB,adelay={burn_delay}:all=1[outfx];"
            f"[abase][outfx]amix=inputs=2:duration=first:normalize=0,"
            f"alimiter=limit={limiter:g}:level={limiter_level}[abody0];"
            f"anullsrc=r=48000:cl=stereo,atrim=0:{OUTRO_BLACK:.6f},asetpts=N/SR/TB[endquiet];"
            f"[abody0][endquiet]concat=n=2:v=0:a=1[abody]")
    else:
        # bundled FILMBURN asset (e.g. filmburn_blue.mp4) has no audio track of its
        # own — skip reusing burn audio instead of feeding ffmpeg a stream that
        # doesn't exist (fails the whole filtergraph with "matches no streams").
        f+=(f";[abase]alimiter=limit={limiter:g}:level={limiter_level}[abody0];"
            f"anullsrc=r=48000:cl=stereo,atrim=0:{OUTRO_BLACK:.6f},asetpts=N/SR/TB[endquiet];"
            f"[abody0][endquiet]concat=n=2:v=0:a=1[abody]")
    if cover:
        cd=1.0/FPS  # Instagram only needs one frame to grab a thumbnail from
        ins+=f' -loop 1 -t {cd} -i "{cover}"'
        cover_idx=7 if music else 6
        f+=(f";[{cover_idx}:v]scale={W}:{H},fps={FPS},format=yuv420p,setsar=1[cv];"
            f"[cv][body]concat=n=2:v=1:a=0[vfin];"
            f"anullsrc=r=48000:cl=stereo,atrim=0:{cd},asetpts=N/SR/TB[sil];"
            f"[sil][abody]concat=n=2:v=0:a=1[afin]")
    else:
        f+=";[body]null[vfin];[abody]anull[afin]"
    encoder=os.environ.get('VIDEO_ENCODER','libx264')
    if encoder=='h264_videotoolbox':
        bitrate=os.environ.get('VT_BITRATE','16M')
        maxrate=os.environ.get('VT_MAXRATE','20M')
        bufsize=os.environ.get('VT_BUFSIZE','32M')
        vopts=(f'-c:v h264_videotoolbox -b:v {bitrate} -maxrate {maxrate} '
               f'-bufsize {bufsize} -profile:v high -allow_sw 0 -realtime 1 '
               f'-prio_speed 1 -pix_fmt nv12')
    else:
        vopts=f'-c:v libx264 -preset {preset} -crf {crf} -pix_fmt yuv420p'
    sh(f'ffmpeg -y -v error {ins} -filter_complex "{f}" -map "[vfin]" -map "[afin]" '
       f'{vopts} -c:a aac -b:a 160k '
       f'{extra} -movflags +faststart "{out}"')

if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json'))); k=sys.argv[1]; c=P[k]
    passA(c,f'{B}/A_{k}.mp4'); print('passA ok')
    make_intro(f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4'); print('intro ok')
    final(c,f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4',f'{B}/{k}_vertical.mp4'); print('final ok')
