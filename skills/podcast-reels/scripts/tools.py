#!/usr/bin/env python3
"""Fast review helpers. Never render a full clip just to look at a caption.

  JOB=job.json python3 tools.py sheet corte01            # 8-frame contact sheet
  JOB=job.json python3 tools.py probe corte01 12 18      # 6s @540p, captions only
"""
import os,sys,json,subprocess
HERE=os.path.dirname(os.path.abspath(__file__))
JOB=json.load(open(os.environ['JOB'])); B=JOB.get('work','./work')
def sh(c):
    r=subprocess.run(c,shell=True,capture_output=True,text=True)
    if r.returncode: print(r.stderr[-2000:]); raise SystemExit(1)

def sheet(k,n=8):
    src=f'{B}/V_{k}.mp4'
    if not os.path.exists(src): src=os.path.join(JOB.get('outdir',B),f'{k}.mp4')
    d=float(subprocess.run(f'ffprobe -v error -show_entries format=duration -of csv=p=0 "{src}"',
        shell=True,capture_output=True,text=True).stdout)
    sel='+'.join("eq(n\\,%d)"%int(d*30*(i+0.5)/n) for i in range(n))
    out=f'{B}/sheet_{k}.png'
    sh(f'ffmpeg -y -v error -i "{src}" -vf "select=\'{sel}\',crop=1080:520:0:730,scale=380:-1,tile=2x4" '
       f'-frames:v 1 -fps_mode vfr "{out}"')
    print(out); return out

def probe(k,t0,t1):
    """caption band over the cut, no burn/intro/cover - seconds are FINAL-cut time"""
    a=f'{B}/A_{k}.mp4'; cr=f'{B}/caps_{k}_rgb.mp4'; ca=f'{B}/caps_{k}_a.mp4'
    out=f'{B}/probe_{k}.mp4'
    f=(f"[0:v]trim={t0}:{t1},setpts=PTS-STARTPTS[v];"
       f"[1:v]trim={t0}:{t1},setpts=PTS-STARTPTS,format=yuva420p[c];"
       f"[2:v]trim={t0}:{t1},setpts=PTS-STARTPTS[m];[c][m]alphamerge[cap];"
       f"[v][cap]overlay=0:810,scale=540:960[vo];"
       f"[0:a]atrim={t0}:{t1},asetpts=PTS-STARTPTS[ao]")
    sh(f'ffmpeg -y -v error -i "{a}" -i "{cr}" -i "{ca}" -filter_complex "{f}" '
       f'-map "[vo]" -map "[ao]" -c:v libx264 -preset ultrafast -crf 24 -c:a aac "{out}"')
    print(out); return out

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='sheet': sheet(sys.argv[2],int(sys.argv[3]) if len(sys.argv)>3 else 8)
    else: probe(sys.argv[2],float(sys.argv[3]),float(sys.argv[4]))
