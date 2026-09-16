"""Render completo de um video de produto da Fernanda a partir de job.json.

Uso:
  python3 render.py job.json prep     # camada de legenda, trilha de burn e trilha de SFX
  python3 render.py job.json check    # valida o grafo processando 0,5 s
  python3 render.py job.json render   # MP4 editavel (A1 voz+SFX, A2 musica) + copia mixada para postar

Tempos de job.json (in, out, cuts, broll, zooms) sao do ARQUIVO ORIGINAL; o script converte.
"""
import json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from timeline import load_job, segments, duration, o, cut_points

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = f"{SKILL}/assets"
LUT = f"{A}/SLog3SGamut3.CineToLC-709TypeA.cube"
FB = f"{A}/filmburn_blue.mp4"
WHOOSH = f"{A}/film_burn_transitions_sfx_source.mp4"
CLICK = f"{A}/camera_click.mp3"
WHOOSH_PEAKS = [6.40, 9.90, 13.35, 14.70, 19.90, 21.35, 24.60, 25.80]  # picos dos whooshes no arquivo original

job = load_job(sys.argv[1])
MODE = sys.argv[2]
W = job["work"]; os.makedirs(W, exist_ok=True)
D = duration(job)
SEGS = segments(job)
BR = [(b["file"], b.get("ss", 0.0), o(job, b["start"]), o(job, b["end"])) for b in job["broll"]]
# blocos de tela dividida: referencias encostadas viram um bloco so (troca sem burn, so clique)
BLOCKS = []
for _, _, a, b in BR:
    if BLOCKS and abs(BLOCKS[-1][1] - a) < 0.05:
        BLOCKS[-1] = (BLOCKS[-1][0], b)
    else:
        BLOCKS.append((a, b))
ZOOMS = [o(job, z) for z in job.get("zooms", [])]
PUNCHES = cut_points(job)
SHIFT, PANEL, SEAM = job.get("shift", 850), 1500, 220
CAP_Y_NORMAL, CAP_Y_SPLIT = 2022, 1350
MUS = job.get("music", {})
MUSIC_OFFSET = MUS.get("offset", "auto")
if MUSIC_OFFSET == "auto":
    MUSIC_OFFSET = round(MUS.get("track_end", 93.2) - D, 2)  # final natural da faixa coincide com o fim do video
EDIT = os.path.join(job["out_dir"], f'{job["name"]} - final com referencias.mp4')
POST = os.path.join(job["out_dir"], f'{job["name"]} - final (mix pronto para postar).mp4')


def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


def zoom_expr():
    """Zoom suave (0,6 s in, 12%) com volta lenta (4 s), mais zoom seco (10%, volta em 3 s) em cada corte.
    Os termos sao combinados com max(); somar termos que se sobrepoem dobra o zoom."""
    terms = []
    for t0 in ZOOMS:
        end = t0 + 4.6
        for p in PUNCHES:
            if t0 < p < end:
                end = p
        a = f"(t-{t0})"
        terms.append(f"if(between(t,{t0},{t0 + 0.6}),1+0.12*(0.5-0.5*cos(PI*{a}/0.6)),"
                     f"if(between(t,{t0 + 0.6},{end}),1+0.12*(0.5+0.5*cos(PI*({a}-0.6)/4.0)),1))")
    for p in PUNCHES:
        terms.append(f"if(between(t,{p},{p + 3.0}),1+0.10*(0.5+0.5*cos(PI*(t-{p})/3.0)),1)")
    if not terms:
        return "1"
    e = terms[0]
    for t in terms[1:]:
        e = f"max({e},{t})"
    return e


def build_track():
    bt = [0.0] + [t - 0.53 for b in BLOCKS for t in b] + [D - 0.62]  # pico do burn (0,53 s) em cada emenda
    ins = " ".join(f'-i "{FB}"' for _ in bt)
    f = f"color=black:s=1080x1920:r=30000/1001:d={D},format=gbrp[y];"
    prev = "y"
    for i, t in enumerate(bt):
        f += (f"[{i}:v]fps=30000/1001,format=gbrp,tpad=start_mode=add:start_duration={max(t, 0):.3f}:color=black,"
              f"tpad=stop_mode=add:stop_duration={D + 2}:color=black,trim=duration={D}[x{i}];"
              f"[{prev}][x{i}]blend=all_mode=screen[y{i}];")
        prev = f"y{i}"
    f += f"[{prev}]format=yuv422p10le[out]"
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[out]" -c:v prores_videotoolbox -profile:v proxy "{W}/burntrack.mov"')


def build_sfx():
    PRE, POST_ = 0.55, 0.75
    ins, f, labels, n = "", "", [], 0
    for i, t in enumerate([t for b in BLOCKS for t in b]):  # whoosh so nas entradas/saidas das referencias
        p = WHOOSH_PEAKS[i % len(WHOOSH_PEAKS)]
        ins += f'-ss {p - PRE:.2f} -t {PRE + POST_:.2f} -i "{WHOOSH}" '
        ms = int(max(t - PRE, 0) * 1000)
        f += (f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.08,"
              f"afade=t=out:st={PRE + POST_ - 0.25:.2f}:d=0.25,volume=-7dB,adelay={ms}|{ms}[w{n}];")
        labels.append(f"[w{n}]"); n += 1
    for _, _, a, _ in BR:  # clique quando a referencia aparece ou troca
        ins += f'-ss 0.10 -t 0.40 -i "{CLICK}" '
        ms = int(max(a - 0.05, 0) * 1000)
        f += f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-4dB,adelay={ms}|{ms}[w{n}];"
        labels.append(f"[w{n}]"); n += 1
    f += f"anullsrc=r=48000:cl=stereo:d={D}[z];[z]{''.join(labels)}amix=inputs={n + 1}:duration=first:normalize=0[out]"
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[out]" -t {D} -c:a pcm_s16le "{W}/sfx_track.wav"')


def graph():
    z = zoom_expr()
    rot = "transpose=clock," if job.get("rotate", "clock") == "clock" else ""
    ins = f'-noautorotate -i "{job["src"]}" -i "{W}/burntrack.mov" -i "{W}/caps.mov" '
    n = len(SEGS)
    f = f"[0:v]{rot}split={n}" + "".join(f"[vs{i}]" for i in range(n)) + ";"
    for i, (a, b) in enumerate(SEGS):
        f += f"[vs{i}]trim={a}:{b},setpts=PTS-STARTPTS[vt{i}];"
    f += "".join(f"[vt{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0,fps=30000/1001,"
    # zoom por crop dinamico + scale fixo. NAO usar scale(eval=frame)+crop('(iw-2160)/2'): o crop guarda o iw
    # da configuracao inicial e o zoom ancora no canto superior esquerdo (ela "escorrega" para a direita).
    f += (f"crop=w='2160/({z})':h='3840/({z})':x='(2160-2160/({z}))/2':y='(3840-3840/({z}))*0.38',"
          f"scale=2160:3840:flags=bicubic,setsar=1,format=rgb48le,lut3d={LUT}:interp=tetrahedral,"
          f"hue=s=0.88,colortemperature=temperature=6200:mix=0.35,eq=contrast=1.03:gamma=1.02,format=yuv420p,split[sk0][sk1];"
          f"[sk1]scale=1080:1920,bilateral=sigmaS=6:sigmaR=0.06:planes=7,scale=2160:3840:flags=bicubic[sks];"
          f"[sk0][sks]mix=inputs=2:weights='0.7 0.3',split[m][s];"
          f"[s]crop=2160:{3840 - SHIFT}:0:0,pad=2160:3840:0:{SHIFT}:black[sh0];")
    prev = "sh0"
    for k, (file, ss, a, b) in enumerate(BR):
        ins += f'-ss {ss} -t {b - a + 0.3} -i "{file}" '
        f += (f"[{3 + k}:v]fps=30000/1001,scale=2160:{PANEL}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop=2160:{PANEL},setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{a}/TB[r{k}];"
              f"[{prev}][r{k}]overlay=0:0:eof_action=pass:enable='between(t,{a},{b})'[sh{k + 1}];")
        prev = f"sh{k + 1}"
    en = "+".join(f"between(t,{a},{b})" for a, b in BLOCKS) or "0"
    SH = SEAM // 2
    f += (f"[m][{prev}]overlay=0:0:enable='{en}'[comp0];"
          f"[comp0]split[cA][cB];[cB]crop=2160:{SEAM}:0:{PANEL - SH},gblur=sigma=16,format=yuva444p[sb];"
          f"color=black:s=2160x{SEAM}:r=30000/1001,format=gray,geq=lum='255*pow(max(0\\,1-abs(Y-{SH})/{SH})\\,0.8)'[sm];"
          f"[sb][sm]alphamerge[sba];[cA][sba]overlay=0:{PANEL - SH}:shortest=1:enable='{en}'[comp];"
          f"[2:v]split[c1][c2];"
          f"[comp][c1]overlay=0:{CAP_Y_NORMAL}:eof_action=pass:enable='not({en})'[k1];"
          f"[k1][c2]overlay=0:{CAP_Y_SPLIT}:eof_action=pass:enable='{en}'[k2];"
          f"[1:v]scale=2160:3840:flags=bicubic,format=gbrp[bt];[k2]format=gbrp[k2g];"
          f"[k2g][bt]blend=all_mode=screen:shortest=1,format=yuv420p,fade=t=out:st={D - 0.35}:d=0.35[vo];")
    f += f"[0:a]asplit={n}" + "".join(f"[as{i}]" for i in range(n)) + ";"
    for i, (a, b) in enumerate(SEGS):
        f += f"[as{i}]atrim={a}:{b},asetpts=PTS-STARTPTS[at{i}];"
    prev = "at0"
    for i in range(1, n):
        f += f"[{prev}][at{i}]acrossfade=d=0.015:c1=tri:c2=tri[ax{i}];"
        prev = f"ax{i}"
    f += f"[{prev}]afade=t=in:d=0.05,afade=t=out:st={D - 0.35}:d=0.35[voice];"
    ins += f'-i "{W}/sfx_track.wav" '
    f += (f"[{3 + len(BR)}:a]volume={job.get('sfx_db', -6)}dB[sfx];[voice][sfx]amix=inputs=2:duration=first:normalize=0,"
          f"alimiter=limit=0.95:level=false,asplit[ao][sc];")
    ins += f'-ss {MUSIC_OFFSET} -t {D + 1} -i "{MUS["file"]}" '
    f += (f"[{4 + len(BR)}:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=35,volume={MUS.get('db', -20.5)}dB,"
          f"afade=t=in:d=0.3,afade=t=out:st={D - 0.6}:d=0.6[mus];"
          f"[mus][sc]sidechaincompress=threshold=0.03:ratio=4:attack=20:release=450:makeup=1[mo]")
    return ins, f


if MODE == "prep":
    print("duracao", D, "trechos", SEGS, "\nreferencias", BR, "\nblocos", BLOCKS, "\nzooms", ZOOMS, "cortes", PUNCHES)
    run(f'python3 "{SKILL}/scripts/caps_layer.py" "{job["captions"]}" {D} "{W}/caps.mov"')
    build_track(); build_sfx()
elif MODE == "check":
    ins, f = graph()
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[vo]" -map "[ao]" -map "[mo]" -t 0.5 -f null -')
elif MODE == "render":
    ins, f = graph()
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[vo]" -map "[ao]" -map "[mo]" -t {D} -c:v h264_videotoolbox '
        f'-metadata:s:a:0 title="Voz + SFX" -metadata:s:a:1 title="Musica" -disposition:a:0 default -disposition:a:1 0 '
        f'-b:v 45M -maxrate 60M -profile:v high -tag:v avc1 -color_range tv -colorspace bt709 -color_primaries bt709 '
        f'-color_trc bt709 -c:a aac -b:a 320k -movflags +faststart "{EDIT}"')
    run(f'ffmpeg -v error -y -i "{EDIT}" -filter_complex "[0:a:0][0:a:1]amix=inputs=2:duration=first:normalize=0,'
        f'alimiter=limit=0.95:level=false[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 320k -movflags +faststart "{POST}"')
print("OK", MODE)
