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

def caption_y_expr(c,base_y=810):
    """Captions are timed for the full-frame talking head. During a broll
    split-screen event the head is pushed down by panel_h pixels, so the
    caption must shift down by the same amount for that window or it lands
    on the (now higher-in-frame) face instead of below the chin."""
    terms=[str(c.get('caption_base_y') or base_y)]
    for event in c.get('broll',[]):
        start=float(event['t']); duration=float(event.get('duration',4.6)); end=start+duration
        panel_h=int(event.get('height',610))
        lo=start+0.16; hi=end-0.10
        if hi>lo:
            terms.append(f"{panel_h}*between(t,{lo:.6f},{hi:.6f})")
    return '+'.join(terms)

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

def color_grade(c):
    """Apply a restrained Rec.709 grade before captions and brand overlays."""
    grade=c.get('grade',{})
    filters=[]
    curves=grade.get('curves')
    if curves:
        filters.append(f"curves=all='{curves}'")
    eq=[]
    for key in ('brightness','contrast','saturation','gamma'):
        if key in grade:
            eq.append(f'{key}={float(grade[key]):g}')
    if eq:
        filters.append('eq='+':'.join(eq))
    return (','+','.join(filters)) if filters else ''

def passA(c,out):
    keeps=c['keeps']; n=len(keeps); fc=[]
    # The 9:16 window is derived from the SOURCE height so masters below 1080p
    # are cropped at their native resolution and upscaled once, at the end.
    _dims=sh(f'ffprobe -v error -select_streams v:0 -show_entries stream=height '
             f'-of csv=p=0 "{os.path.join(SRCDIR,c["src"])}"').strip().split(',')[0]
    srch=int(float(_dims))//2*2
    cw=int(round(srch*9/16))//2*2
    timeline=sorted((float(t),float(x)) for t,x in c.get('cropx_timeline',[]))
    # Hard-cut zoom steps: each keep segment gets its own crop window, so the
    # framing jumps between near and wide on the edit instead of animating.
    zoom_steps=sorted((float(t),float(z)) for t,z in c.get('zoom_steps',[]))
    cropy=float(c.get('cropy',0.5))
    # Per-block vertical framing: when the speaker leans forward his chin drops
    # into the caption band, and captions must stay below the chin — so the head
    # is raised for that block instead of moving the text.
    cropy_steps=sorted((float(t),float(y)) for t,y in c.get('cropy_steps',[]))
    def cropy_at(a):
        current=cropy
        for t,y in cropy_steps:
            if t<=a+1e-6: current=y
        return min(1.0,max(0.0,current))
    def zoom_at(a):
        current=1.0
        for t,z in zoom_steps:
            if t<=a+1e-6: current=z
        return max(1.0,current)
    def crop_expr(a,b,cwi):
        current=float(c['cropx']); changes=[]
        for t,x in timeline:
            if t <= a+1e-6: current=x
            elif t < b-1e-6: changes.append((t-a,x))
        vals=[current]+[x for _,x in changes]
        expr=f'{vals[-1]:.5f}'
        for j in range(len(changes)-1,-1,-1):
            boundary=changes[j][0]
            expr=f'if(lt(t,{boundary:.5f}),{vals[j]:.5f},{expr})'
        return f'(iw-{cwi})*({expr})'
    for i,(a,b) in enumerate(keeps):
        # snap to exact frame boundaries: a fractional-second trim start forces the
        # later `fps={FPS}` filter to duplicate frames to realign, producing a regular
        # every-other-frame stutter that reads as a shake/vibration.
        a=round(a*FPS)/FPS; b=round(b*FPS)/FPS
        d=max(0.2,b-a); N=max(1,int(round(d*FPS))-1)
        z=zoom_at(a)
        cwi=int(round(cw/z))//2*2; chi=int(round(srch/z))//2*2
        x=crop_expr(a,b,cwi)
        y=int(round((srch-chi)*cropy_at(a)))
        vf=(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,"
            f"crop={cwi}:{chi}:x='{x}':y={y}{color_grade(c)},"
            # zoom steps change the crop size, so normalise SAR or concat refuses
            f"scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS}")
        fc.append(vf+f"[v{i}]")
        fade_out=0.120 if i==n-1 else 0.020
        fc.append(f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:st=0:d=0.012,afade=t=out:st={round(b-a-fade_out,3)}:d={fade_out:.3f}[a{i}]")
    fc.append(''.join(f"[v{i}][a{i}]" for i in range(n))+f"concat=n={n}:v=1:a=1[vc][ac]")
    motion=impact_motion(c)
    if c.get('broll'):
        motion=motion.replace('[vo]','[vmotion]')
    fc.append(motion)
    broll_inputs=[]
    previous='vmotion'
    for j,event in enumerate(c.get('broll',[]),start=1):
        path=event['path']
        start=float(event['t']); duration=float(event.get('duration',4.6)); end=start+duration
        panel_h=int(event.get('height',610))
        lower_h=H-panel_h
        # Keep the speaker at the original scale. Cropping the already-vertical
        # talking head again made the lower pane feel cramped and unprofessional.
        main_crop_w=int(event.get('main_crop_w',1080))
        main_crop_h=round(main_crop_w*lower_h/W)
        main_crop_x=int(event.get('main_crop_x',130))
        main_crop_y=int(event.get('main_crop_y',0))
        main_crop_x=max(0,min(W-main_crop_w,main_crop_x))
        main_crop_y=max(0,min(H-main_crop_h,main_crop_y))
        # Reference layout: B-roll occupies the top, while the talking head is
        # re-framed slightly lower. Film burns hide both direct layout switches;
        # there is no fade, sliding pane, or headline between the two images.
        broll_idx=2*j-1; burn_idx=2*j
        broll_inputs.append(f'-stream_loop -1 -i "{path}"')
        broll_inputs.append(f'-stream_loop -1 -i "{os.environ["FILMBURN"]}"')
        fc.append(
            f"[{broll_idx}:v]scale={W}:{panel_h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{panel_h},fps={FPS},setsar=1,trim=duration={duration:.6f},"
            f"format=yuv420p,"
            f"setpts=PTS+{start:.6f}/TB[br{j}]"
        )
        fc.append(
            f"[{previous}]split=2[vbase{j}][vshift{j}];"
            f"[vshift{j}]crop={main_crop_w}:{main_crop_h}:{main_crop_x}:{main_crop_y},"
            f"scale={W}:{lower_h}:flags=lanczos,"
            f"pad={W}:{H}:0:{panel_h}:color=0x000249[stackmain{j}];"
            f"[stackmain{j}][br{j}]overlay=x=0:y=0:eval=frame:eof_action=pass:"
            f"enable='between(t,{start:.6f},{end:.6f})'[stackbr{j}]"
        )
        # Only the lower edge receives treatment: a narrow real blur across the
        # join plus a restrained translucent navy strip below the B-roll.
        seam_h=34
        blur_h=46
        blur_y=max(0,panel_h-10)
        fc.append(
            f"[stackbr{j}]split=2[stackraw{j}][stackblur{j}];"
            f"[stackblur{j}]gblur=sigma=9:steps=2,crop={W}:{blur_h}:0:{blur_y}[blurstrip{j}];"
            f"[stackraw{j}][blurstrip{j}]overlay=0:{blur_y}:eof_action=pass[stacksoft{j}];"
            f"color=c=0x000249@0.32:s={W}x{seam_h}:r={FPS}:d={float(c['total'])+1:.3f},"
            f"format=yuva420p[seam{j}];"
            f"[stacksoft{j}][seam{j}]overlay=0:{panel_h}:eof_action=pass[stackline{j}];"
            f"[vbase{j}][stackline{j}]overlay=0:0:eof_action=pass:"
            f"enable='between(t,{start+0.16:.6f},{end-0.10:.6f})'[vswitch{j}]"
        )
        burn_d=0.46
        burn_in=max(0.0,start-0.08)
        burn_out=max(burn_in+burn_d,end-0.24)
        burn_gap=max(0.001,burn_out-(burn_in+burn_d))
        burn_tail=max(0.001,float(c['total'])-(burn_out+burn_d)+0.15)
        fc.append(
            f"[{burn_idx}:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H},fps={FPS},setsar=1,format=gbrp,split=2[burnin0_{j}][burnout0_{j}];"
            f"[burnin0_{j}]trim=duration={burn_d:.6f},setpts=PTS-STARTPTS[burnin_{j}];"
            f"[burnout0_{j}]trim=duration={burn_d:.6f},setpts=PTS-STARTPTS[burnout_{j}];"
            f"color=c=black:s={W}x{H}:r={FPS}:d={burn_in:.6f},format=gbrp[burnpre_{j}];"
            f"color=c=black:s={W}x{H}:r={FPS}:d={burn_gap:.6f},format=gbrp[burngap_{j}];"
            f"color=c=black:s={W}x{H}:r={FPS}:d={burn_tail:.6f},format=gbrp[burntail_{j}];"
            f"[burnpre_{j}][burnin_{j}][burngap_{j}][burnout_{j}][burntail_{j}]"
            f"concat=n=5:v=1:a=0[burntrack_{j}];"
            f"[vswitch{j}]format=gbrp[vsg_{j}];"
            f"[vsg_{j}][burntrack_{j}]blend=all_mode=screen:shortest=1,format=yuv420p[vline{j}]"
        )
        previous=f'vline{j}'
    if c.get('broll'):
        fc.append(f'[{previous}]format=yuv420p[vo]')
    fc.append("[ac]aresample=48000,asetpts=N/SR/TB[ao]")
    f=';'.join(fc)
    ins=' '.join(broll_inputs)
    sh(f'ffmpeg -y -v error -i "{SRCDIR}/{c["src"]}" {ins} -filter_complex "{f}" -map "[vo]" -map "[ao]" '
       f'-c:v libx264 -preset ultrafast -crf 14 -pix_fmt yuv420p '
       f'-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 '
       f'-c:a aac -b:a 192k "{out}"')

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
    lr=f'{B}/lettering_{k}_rgb.mp4'; la=f'{B}/lettering_{k}_a.mp4'
    ins=(f'-i "{passa}" -i "{intro}" -i "{fb}" -i "{cr}" -i "{ca}" -i "{clk}" '
         f'-i "{lr}" -i "{la}"')
    music=c.get('music')
    mix=c.get('mix',{})
    burn_d=0.80
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
       f"[vb][capa]overlay=x=0:y='{caption_y_expr(c)}':eval=frame:format=auto:eof_action=pass[vcap];"
       f"[6:v]format=yuva420p[l6];[l6][7:v]alphamerge[leta];"
       f"[vcap][leta]overlay=x=0:y=1180:format=auto:eof_action=pass,setsar=1,"
       f"fade=t=out:st={fade_start:.6f}:d={OUTRO_FADE:.6f},format=yuv420p[bodyfade];"
       f"color=c=black:s={W}x{H}:r={FPS}:d={OUTRO_BLACK:.6f},setsar=1,format=yuv420p[endblack];"
       f"[bodyfade][endblack]concat=n=2:v=1:a=0[body];"
       f"[0:a]highpass=f=70,lowpass=f=15500,"
       f"acompressor=threshold=0.14:ratio=2.0:attack=15:release=180:makeup=1.06[dialog];"
       f"[dialog][5:a]amix=inputs=2:duration=first:normalize=0[voice]")
    if music:
        music_db=float(mix.get('music_db',-21))
        music_offset=max(0.0,float(mix.get('music_offset',0)))
        music_fade_out=max(0.0,float(c['total'])-0.8)
        duck_threshold=float(mix.get('duck_threshold',0.08))
        duck_ratio=float(mix.get('duck_ratio',5))
        f+=(f";[8:a]atrim=start={music_offset:.3f},asetpts=PTS-STARTPTS,"
            f"volume={music_db:g}dB,afade=t=in:d=0.8,"
            f"afade=t=out:st={music_fade_out:.3f}:d=0.8[music];"
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
        cover_idx=9 if music else 8
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
       f'-bsf:v h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1:video_full_range_flag=0 '
       f'-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709 '
       f'{extra} -movflags +faststart "{out}"')

if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json'))); k=sys.argv[1]; c=P[k]
    passA(c,f'{B}/A_{k}.mp4'); print('passA ok')
    make_intro(f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4'); print('intro ok')
    final(c,f'{B}/A_{k}.mp4',f'{B}/I_{k}.mp4',f'{B}/{k}_vertical.mp4'); print('final ok')
