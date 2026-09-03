import json,sys,numpy as np,subprocess,wave
import os
SR=48000
def shutter():
    n=int(0.055*SR); t=np.arange(n)/SR
    rng=np.random.default_rng(7)
    noise=rng.standard_normal(n)
    env=np.exp(-t*95)
    a=noise*env
    n2=int(0.035*SR); t2=np.arange(n2)/SR
    b=rng.standard_normal(n2)*np.exp(-t2*160)
    a[:n2]+=b*0.8
    # band-limit: simple one-pole hp + lp
    y=np.copy(a); prev=0
    for k in range(1,len(y)): y[k]=0.92*(y[k-1]+a[k]-a[k-1])
    z=np.copy(y); s=0
    for k in range(len(z)):
        s=s+0.35*(z[k]-s); z[k]=s
    z/= (np.max(np.abs(z))+1e-9)
    z*=0.16
    z[:24]*=np.linspace(0,1,24)
    z[-200:]*=np.linspace(1,0,200)
    return z.astype(np.float32)
def load_sfx(env_name, fallback, default_gain):
    fp=os.environ.get(env_name,'')
    if fp and os.path.exists(fp):
        raw=subprocess.run(f'ffmpeg -v error -i "{fp}" -f s16le -ar {SR} -ac 1 -',
                           shell=True,capture_output=True).stdout
        a=np.frombuffer(raw,dtype='<i2').astype(np.float32)/32768.0
        pk=float(np.abs(a).max()) or 1.0
        a=a/pk*default_gain
        return a.astype(np.float32)
    return fallback()
CL=load_sfx('CLICK',shutter,float(os.environ.get('CLICK_GAIN','0.12')))
WH=load_sfx('WHOOSH',shutter,float(os.environ.get('WHOOSH_GAIN','0.085')))
POP=load_sfx('POP',shutter,float(os.environ.get('POP_GAIN','0.10')))
SFX={'click':CL,'whoosh':WH,'pop':POP}
def build(clip,out):
    dur=clip['total']+0.2
    buf=np.zeros(int(dur*SR),dtype=np.float32)
    marks=clip.get('click_times',[])
    if marks:
        events=[]
        for item in marks:
            if isinstance(item,dict):
                events.append((float(item['t']),item.get('kind','click'),float(item.get('gain',1.0))))
            else:
                events.append((float(item),'click',1.0))
    else:
        events=[(c['s'],'click',1.0) for idx,c in enumerate(clip['caps'])
                if c.get('any') and idx!=0]
    for t,kind,gain in events:
        sound=SFX.get(kind,CL)
        offset=-0.16 if kind=='whoosh' else 0.03
        i=max(0,int((t+offset)*SR))
        j=min(len(buf),i+len(sound))
        buf[i:j]+=sound[:j-i]*gain
    st=np.stack([buf,buf],1)
    st=np.clip(st,-1,1)
    pcm=(st*32767).astype('<i2').tobytes()
    w=wave.open(out,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm); w.close()
if __name__=='__main__':
    P=json.load(open(os.path.join(B,'plan.json'))); k=sys.argv[1]
    build(P[k],os.path.join(B,'clicks_%s.wav'%k)); print('ok')
