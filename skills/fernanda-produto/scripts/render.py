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
# letterings no formato {"block", "main"} (o do fx_layer) nao trazem o tempo: resolve pelo bloco de legenda,
# senao o whoosh do lettering quebra com KeyError 't' (ou fica sem som)
if job.get("letterings"):
    _caps = json.load(open(job["captions"]))
    for _e in job["letterings"]:
        if "t" not in _e:
            _e["t"] = next(c["start"] for c in _caps if _e["block"].lower() in c["text"].replace("\n", " ").lower())
# shift: quanto ela desce na tela dividida. 850 vale para o plano da Fernanda (cabeca em ~y 1000). Com enquadramento
# mais fechado (framings/shots, cabeca perto de y 460) use ~1150, senao o rosto fica atras da referencia.
SHIFT, PANEL, SEAM = job.get("shift", 850), 1500, 220
CAP_Y_NORMAL, CAP_Y_SPLIT = 2022, 1350
FX = bool(job.get("fx"))                 # legenda animada + lettering (fx_layer.py)
CAP_OFF = 30 if FX else 0                # faixa do fx_layer tem baseline em 330 (caps_layer: 300)
LETTER_IN = 5 + len(BR)                  # indice do letter.mov (depois de sfx e musica)
# Motor da Malu (opcional; so o job dela liga): camera_engine "malu" = cortes, enquadramento e zoom saem prontos do
# camera.py (camera.mov); caption_engine "kinetic" = legenda palavra por palavra (kinetic_caps.mov, quadro cheio).
# Sem essas chaves o grafo e identico ao de antes (conferido quadro a quadro num job da Fernanda).
CAM = job.get("camera_engine") == "malu"
KIN = job.get("caption_engine") == "kinetic"
MALU = job.get("engine_scripts", os.path.expanduser("~/.claude/skills/malu-cortes/scripts"))
CAM_IN = 5 + len(BR) + (1 if FX else 0)  # indice do camera.mov (ultima entrada)
# sfx_separate (Malu): no arquivo editavel o SFX vai numa faixa propria (A1 voz, A2 musica, A3 SFX); o ducking da musica
# continua pela voz+SFX. Sem a chave: A1 voz+SFX, A2 musica, como sempre.
SEP = bool(job.get("sfx_separate"))
SXMAP = ' -map "[sxo]"' if SEP else ""
AMIX = "[0:a:0][0:a:1][0:a:2]amix=inputs=3:" if SEP else "[0:a:0][0:a:1]amix=inputs=2:"
AMETA = ('-metadata:s:a:0 title="Voz" -metadata:s:a:1 title="Musica" -metadata:s:a:2 title="SFX" '
         '-disposition:a:0 default -disposition:a:1 0 -disposition:a:2 0 ' if SEP else
         '-metadata:s:a:0 title="Voz + SFX" -metadata:s:a:1 title="Musica" -disposition:a:0 default -disposition:a:1 0 ')
MUS = job.get("music", {})
MUSIC_OFFSET = MUS.get("offset", "auto")
if MUSIC_OFFSET == "auto":
    MUSIC_OFFSET = round(MUS.get("track_end", 93.2) - D, 2)  # final natural da faixa coincide com o fim do video
if "version" in job:  # nomes simples; version vazia = sem sufixo (usuario nao quer v1/v2 acumulando na pasta)
    tag = f' - {job["version"]}' if job["version"] else ""
    _suf = job.get("edit_suffix", "voz e musica separadas")   # "" = sem sufixo no titulo (Malu)
    EDIT = os.path.join(job["out_dir"], f'{job["name"]}{tag}' + (f' ({_suf})' if _suf else '') + '.mp4')
    POST = os.path.join(job["out_dir"], f'{job["name"]}{tag} (mix pronto para postar).mp4')
else:
    EDIT = os.path.join(job["out_dir"], f'{job["name"]} - final com referencias.mp4')
    POST = os.path.join(job["out_dir"], f'{job["name"]} - final (mix pronto para postar).mp4')


# limite 0,84 (~-1,5 dBFS): 0,89 segurava o pico por amostra, mas o true peak passava de -1 dBTP
TAGS = "-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv "


def run(cmd):
    subprocess.run(cmd, shell=True, check=True)


# zoom_in: duracao da entrada do zoom suave (0,6 s = padrao Fernanda). Usuario, reel da Malu: "zoom in mais rapido
# com um pouco de blur e zoom out mais lerdo" -> zoom_in 0.3, zoom_blur true e smooth_zooms com 6-7 s de volta.
ZIN = float(job.get("zoom_in", 0.6))
ZOUT = float(job.get("zoom_out", 4.0))


def zoom_blur(starts):
    """Blur de movimento so durante a entrada do zoom: mistura de 4 quadros (tmix) sobreposta nessa janela."""
    if not job.get("zoom_blur") or not starts:
        return ""
    en = "+".join(f"between(t,{t0:.3f},{t0 + ZIN:.3f})" for t0 in starts)
    # zoom_blur_mix: mistura de quadros do blur. 4 iguais deu "fantasma" pesado (rosto ilegivel); na Malu o
    # aprovado e 3 quadros com peso no atual: "frames=3:weights='1 2 4'" (um pouco de blur, rosto legivel)
    mix = job.get("zoom_blur_mix", "frames=4")
    return f"split[zb0][zb1];[zb1]tmix={mix}[zbm];[zb0][zbm]overlay=0:0:enable='{en}',"


def kf_expr(keys):
    """Keyframes [[t, v], ...] (t a partir do inicio do plano) -> expressao linear por partes para o crop."""
    e = str(keys[-1][1])
    for (t0, v0), (t1, v1) in reversed(list(zip(keys[:-1], keys[1:]))):
        e = f"if(lt(t,{t1}),{v0}+({v1 - v0})*(t-{t0})/{max(t1 - t0, 1e-3)},{e})"
    return e


def zoom_expr():
    """Zoom suave (0,6 s in, 12%) com volta lenta (4 s), mais zoom seco (10%, volta em 3 s) em cada corte.
    Os termos sao combinados com max(); somar termos que se sobrepoem dobra o zoom."""
    terms = []
    for t0 in ZOOMS:
        end = t0 + ZIN + ZOUT
        for p in PUNCHES:
            if t0 < p < end:
                end = p
        a = f"(t-{t0})"
        terms.append(f"if(between(t,{t0},{t0 + ZIN}),1+0.12*(0.5-0.5*cos(PI*{a}/{ZIN})),"
                     f"if(between(t,{t0 + ZIN},{end}),1+0.12*(0.5+0.5*cos(PI*({a}-{ZIN})/{ZOUT})),1))")
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
    # whoosh_post: cauda do whoosh depois da emenda (0,75 = padrao Fernanda). Na Malu a fala volta logo depois da
    # saida da referencia e a cauda encostava na fala (-30 dB sobre fala -24 dB): use ~0,35.
    PRE, POST_ = 0.55, float(job.get("whoosh_post", 0.75))
    ins, f, labels, n = "", "", [], 0
    for i, t in enumerate([t for b in BLOCKS for t in b]):  # whoosh so nas entradas/saidas das referencias
        p = WHOOSH_PEAKS[i % len(WHOOSH_PEAKS)]
        ins += f'-ss {p - PRE:.2f} -t {PRE + POST_:.2f} -i "{WHOOSH}" '
        ms = int(max(t - PRE, 0) * 1000)
        f += (f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.08,"
              f"afade=t=out:st={PRE + POST_ - 0.25:.2f}:d=0.25,volume=-7dB,adelay={ms}|{ms}[w{n}];")
        labels.append(f"[w{n}]"); n += 1
    for k, e in enumerate(job.get("letterings", [])):  # whoosh curto e baixo na entrada de cada lettering
        p = WHOOSH_PEAKS[(k + 3) % len(WHOOSH_PEAKS)]
        ins += f'-ss {p - 0.35:.2f} -t 0.8 -i "{WHOOSH}" '
        ms = int(max(e["t"] - 0.25, 0) * 1000)
        f += (f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:d=0.05,afade=t=out:st=0.55:d=0.25,"
              f"volume=-13dB,adelay={ms}|{ms}[w{n}];")
        labels.append(f"[w{n}]"); n += 1
    # click_lead: quanto o clique vem antes da entrada da referencia (0,05 = padrao Fernanda). Se a fala comeca
    # colada no corte (Malu: "Primeiro voce toma..."), 0,05 poe o clique em cima da fala: use ~0,3 (cai na pausa).
    CL = float(job.get("click_lead", 0.05))
    for _, _, a, _ in BR:  # clique quando a referencia aparece ou troca
        ins += f'-ss 0.10 -t 0.40 -i "{CLICK}" '
        ms = int(max(a - CL, 0) * 1000)
        f += f"[{n}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=-4dB,adelay={ms}|{ms}[w{n}];"
        labels.append(f"[w{n}]"); n += 1
    f += f"anullsrc=r=48000:cl=stereo:d={D}[z];[z]{''.join(labels)}amix=inputs={n + 1}:duration=first:normalize=0[out]"
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[out]" -t {D} -c:a pcm_s16le "{W}/sfx_track.wav"')


def graph():
    z = zoom_expr()
    rot = "transpose=clock," if job.get("rotate", "clock") == "clock" else ""
    # -display_rotation 0: o ffmpeg 7+ copia a Display Matrix (-90) da camera para a saida e o player gira o video ja em pe
    caps_file = "kinetic_caps.mov" if KIN else "caps.mov"
    ins = f'-display_rotation 0 -noautorotate -i "{job["src"]}" -i "{W}/burntrack.mov" -i "{W}/{caps_file}" '
    n = len(SEGS)
    # shots: [[a, b, nivel]] em tempo do original cobrindo exatamente os trechos; cada nivel e um enquadramento
    # fixo (framings[nivel] = [x, y, w, h]) -> troca de nivel = corte seco que aumenta/diminui o zoom
    SHOTS = job.get("shots") or [[a, b, None] for a, b in SEGS]
    m = len(SHOTS)
    f = f"[0:v]{rot}split={m}" + "".join(f"[vs{i}]" for i in range(m)) + ";"
    for i, (a, b, lv) in enumerate(SHOTS):
        if lv is not None:
            fm = job["framings"][lv]
            if isinstance(fm, dict):   # plano seguido (face_track.py): posicao do recorte animada por keyframes
                fw_, fh_ = fm["w"], fm["h"]
                fr = f",crop=w={fw_}:h={fh_}:x='{kf_expr(fm['kx'])}':y='{kf_expr(fm['ky'])}',scale=2160:3840:flags=lanczos,setsar=1"
            else:
                fx_, fy_, fw_, fh_ = fm
                fr = f",crop=w={fw_}:h={fh_}:x={fx_}:y={fy_},scale=2160:3840:flags=lanczos,setsar=1"
        else:
            fr = ""
        f += f"[vs{i}]trim={a}:{b},setpts=PTS-STARTPTS{fr}[vt{i}];"
    # tail_hold: congela o ultimo quadro (continuar o video mostraria ela falando a frase seguinte sem som)
    hold = f"tpad=stop_mode=clone:stop_duration={job['tail_hold']}," if job.get("tail_hold") else ""
    f += "".join(f"[vt{i}]" for i in range(m)) + f"concat=n={m}:v=1:a=0,fps=30000/1001,{hold}"
    if CAM:
        f = ""                     # cortes, enquadramento, zoom e tail_hold ja vem prontos no camera.mov
    if job.get("shots"):
        z, bz = "1", 1.0
    # ATENCAO (ffmpeg 9): o crop avalia w/h uma vez so; o zoom abaixo vira deslocamento lateral. Prefira "shots".
    # zoom por crop dinamico + scale fixo. NAO usar scale(eval=frame)+crop('(iw-2160)/2'): o crop guarda o iw
    # da configuracao inicial e o zoom ancora no canto superior esquerdo (ela "escorrega" para a direita).
    # base_zoom: enquadramento fixo mais fechado (material aberto, p.ex. ela sentada de corpo inteiro)
    else:
        bz = job.get("base_zoom", 1.0)
    ay = job.get("anchor_y", 0.38)
    z = f"{bz}*({z})" if bz != 1.0 else z
    # grade: "slog3" (padrao, camera em S-Log3) ou "rec709" (material ja em Rec.709: sem LUT, so ajuste leve)
    if job.get("grade", "slog3") == "rec709":
        color = "format=yuv420p," + job.get("rec709_eq", "eq=contrast=1.03:saturation=0.96") + ","
    else:
        color = (f"format=rgb48le,lut3d={LUT}:interp=tetrahedral,"
                 f"hue=s=0.88,colortemperature=temperature=6200:mix=0.35,eq=contrast=1.03:gamma=1.02,")
    if CAM:
        f += f"[{CAM_IN}:v]setpts=PTS-STARTPTS,{color}format=yuv420p,split[sk0][sk1];"
    elif job.get("shots"):
        # zoom suave estilo Fernanda (12% em 0,6 s, volta ate o fim do plano) SOMADO aos cortes secos.
        # scale por quadro (eval=frame) + crop central por in_w/in_h: ampliar e recortar o centro funciona;
        # o contrario (crop com w/h animados) nao, porque o crop avalia w/h uma vez so e o zoom vira deslocamento.
        ZA = float(job.get("zoom_amount", 0.12))     # 0,12 = padrao Fernanda; Malu 0,14 (rosto chega ao centro exato)
        SZ = job.get("smooth_zooms", [])

        def zz_at(shift=0.0):
            """Fator de zoom em t+shift (shift = amostra dentro do obturador, para o motion blur)."""
            T = f"(t+{shift:.5f})" if shift else "t"
            terms = []
            for t0, t1 in SZ:
                out = max(1.2, t1 - t0 - ZIN)
                terms.append(f"if(between({T},{t0},{t0 + ZIN}),1+{ZA}*(0.5-0.5*cos(PI*({T}-{t0})/{ZIN})),"
                             f"if(between({T},{t0 + ZIN},{t0 + ZIN + out}),1+{ZA}*(0.5+0.5*cos(PI*({T}-{t0}-{ZIN})/{out})),0))")
            return "max(1," + "+".join(terms) + ")"

        # zoom_center_face (Malu): ancora no rosto. Os olhos ficam na mesma altura e o rosto vai do espaco de
        # olhar (fx) para o CENTRO no auge do zoom ("a convidada nao ta 100% centralizada no zoom"). O zoom no
        # centro do quadro fazia o rosto, que fica em 0,44 da largura, escorregar para o lado.
        if job.get("zoom_center_face") and job.get("face_pos"):
            bounds, acc_ = [], 0.0
            for s0, s1, _ in SHOTS:
                acc_ += s1 - s0; bounds.append(round(acc_, 3))
            def pw(vals):
                e = str(vals[-1])
                for tb, v in reversed(list(zip(bounds[:-1], vals[:-1]))):
                    e = f"if(lt(t,{tb}),{v},{e})"
                return e
            FXe = pw([p_[0] for p_ in job["face_pos"]]); EYe = pw([p_[1] for p_ in job["face_pos"]])
            xz = (f"max(0,min(in_w-2160,({FXe})*in_w-(({FXe})+(0.5-({FXe}))*min(1,(in_w/2160-1)/{ZA}))*2160))")
            yz = f"max(0,min(in_h-3840,(in_h-3840)*({EYe})))"
        else:
            xz, yz = "(in_w-2160)/2", f"(in_h-3840)*{ay}"

        def zoom_chain(shift=0.0):
            zz_ = zz_at(shift)
            return (f"scale=w='trunc(2160*({zz_})/2)*2':h='trunc(3840*({zz_})/2)*2':eval=frame:flags=bicubic,"
                    f"crop=w=2160:h=3840:x='{xz}':y='{yz}',setsar=1")

        if SZ and job.get("zoom_shutter"):
            # motion blur de camera (shutter angle, como o Transform do Premiere): cada quadro da entrada do zoom
            # e a media de N amostras do zoom dentro do obturador (360 = intervalo inteiro entre quadros).
            # Nao mistura quadros diferentes no tempo (o tmix fazia fantasma de mao e boca): so a camera borra,
            # em raios a partir do rosto. So nas janelas de entrada, para nao multiplicar o custo do render.
            N = int(job.get("zoom_samples", 10)); SH = float(job["zoom_shutter"]) / 360 / (30000 / 1001)
            f += f"split={1 + len(SZ)}[zpre0]" + "".join(f"[zpre{k + 1}]" for k in range(len(SZ))) + ";"
            f += f"[zpre0]{zoom_chain()}[zmain];"
            prev = "zmain"
            for k, (t0, _) in enumerate(SZ):
                a0, a1 = max(0.0, t0 - 0.1), t0 + ZIN + 0.1
                f += f"[zpre{k + 1}]trim=start={a0:.3f}:end={a1:.3f},split={N}" + "".join(f"[zb{k}_{q}]" for q in range(N)) + ";"
                for q in range(N):
                    f += f"[zb{k}_{q}]{zoom_chain(((q + 0.5) / N - 0.5) * SH)}[zc{k}_{q}];"
                f += "".join(f"[zc{k}_{q}]" for q in range(N)) + f"mix=inputs={N}[zm{k}];"
                f += f"[{prev}][zm{k}]overlay=0:0:eof_action=pass:enable='between(t,{t0},{t0 + ZIN})'[zo{k}];"
                prev = f"zo{k}"
            f += f"[{prev}]{color}format=yuv420p,split[sk0][sk1];"
        else:
            zoom = (zoom_chain() + ",") if SZ else ""
            f += f"{zoom}setsar=1," + zoom_blur([t0 for t0, _ in SZ]) + f"{color}format=yuv420p,split[sk0][sk1];"
    else:
        # enquadramento fixo (base_zoom) + zoom animado (suave e seco nos cortes) por scale eval=frame + crop central.
        # NAO usar crop com w/h animados: o crop avalia w/h uma vez so e o "zoom" vira deslocamento lateral.
        zz = zoom_expr()
        bw, bh = int(2160 / bz) // 2 * 2, int(3840 / bz) // 2 * 2
        f += (f"crop=w={bw}:h={bh}:x={(2160 - bw) // 2}:y={int((3840 - bh) * ay)},scale=2160:3840:flags=lanczos,setsar=1,")
        if zz != "1":
            f += (f"scale=w='trunc(2160*({zz})/2)*2':h='trunc(3840*({zz})/2)*2':eval=frame:flags=bicubic,"
                  f"crop=w=2160:h=3840:x='(in_w-2160)/2':y='(in_h-3840)*{ay}',setsar=1," + zoom_blur(ZOOMS))
        f += f"{color}format=yuv420p,split[sk0][sk1];"
    f += (f"[sk1]scale=1080:1920,bilateral=sigmaS=6:sigmaR=0.06:planes=7,scale=2160:3840:flags=bicubic[sks];"
          f"[sk0][sks]mix=inputs=2:weights='0.7 0.3',split[m][s];"
          f"[s]crop=2160:{3840 - SHIFT}:0:0,pad=2160:3840:0:{SHIFT}:black[sh0];")
    prev = "sh0"
    for k, (file, ss, a, b) in enumerate(BR):
        ins += f'-ss {ss} -t {b - a + 0.3} -i "{file}" '
        # ref_push (opcional, estilo Malu): push lento dentro do painel (1 -> 1+ref_push ao longo da referencia),
        # para o stock nao ficar parado. Sem a chave, painel estatico como no padrao Fernanda.
        rp = float(job.get("ref_push", 0))
        push = (f"scale=w='trunc(2160*(1+{rp}*t/{b - a:.3f})/2)*2':h='trunc({PANEL}*(1+{rp}*t/{b - a:.3f})/2)*2':eval=frame:flags=bicubic,"
                f"crop=2160:{PANEL}," if rp else "")
        f += (f"[{3 + k}:v]fps=30000/1001,scale=2160:{PANEL}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop=2160:{PANEL},setpts=PTS-STARTPTS,{push}setsar=1,format=yuv420p,setpts=PTS-STARTPTS+{a}/TB[r{k}];"
              f"[{prev}][r{k}]overlay=0:0:eof_action=pass:enable='between(t,{a},{b})'[sh{k + 1}];")
        prev = f"sh{k + 1}"
    en = "+".join(f"between(t,{a},{b})" for a, b in BLOCKS) or "0"
    SH = SEAM // 2
    f += (f"[m][{prev}]overlay=0:0:enable='{en}'[comp0];"
          f"[comp0]split[cA][cB];[cB]crop=2160:{SEAM}:0:{PANEL - SH},gblur=sigma=16,format=yuva444p[sb];"
          f"color=black:s=2160x{SEAM}:r=30000/1001,format=gray,geq=lum='255*pow(max(0\\,1-abs(Y-{SH})/{SH})\\,0.8)'[sm];"
          f"[sb][sm]alphamerge[sba];[cA][sba]overlay=0:{PANEL - SH}:shortest=1:enable='{en}'[comp];"
          # KIN: a camada da Malu ja traz cada bloco na altura certa (queixo ou layout) em quadro cheio
          + ((f"[comp]noise=alls={job['grain']}:allf=t[compg];[compg]" if job.get("grain") else "[comp]")
             + "[2:v]overlay=0:0:eof_action=pass[k2l];" if KIN else
             f"[2:v]split[c1][c2];"
             f"[comp][c1]overlay=0:{CAP_Y_NORMAL - CAP_OFF}:eof_action=pass:enable='not({en})'[k1];"
             f"[k1][c2]overlay=0:{CAP_Y_SPLIT - CAP_OFF}:eof_action=pass:enable='{en}'[k2l];")
          + (f"[k2l][{LETTER_IN}:v]overlay=0:{job.get('letter_y', 380)}:eof_action=pass[k2];" if FX else "[k2l]null[k2];")
          # burn: false (Malu): sem o film burn azul da Fernanda (transicao de template, fora da paleta dela)
          + (f"[1:v]scale=2160:3840:flags=bicubic,format=gbrp[bt];[k2]format=gbrp[k2g];"
             f"[k2g][bt]blend=all_mode=screen:shortest=1," if job.get("burn", True) else "[k2]")
          + f"format=yuv420p,fade=t=out:st={D - 0.35}:d=0.35"
          + (f",scale={job['out_size'][0]}:{job['out_size'][1]}:flags=lanczos,setsar=1" if job.get("out_size") else "")
          + "[vo];")
    f += f"[0:a]asplit={n}" + "".join(f"[as{i}]" for i in range(n)) + ";"
    for i, (a, b) in enumerate(SEGS):
        f += f"[as{i}]atrim={a}:{b},asetpts=PTS-STARTPTS[at{i}];"
    # fades de 5 ms por trecho + concat: sem acrossfade, que encurtava 15 ms por corte e tirava a boca de sincronia
    for i, (a, b) in enumerate(SEGS):
        f += f"[at{i}]afade=t=in:d=0.005,afade=t=out:st={b - a - 0.005:.3f}:d=0.005[af{i}];"
    f += "".join(f"[af{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1," + (f"apad=pad_dur={job['tail_hold']}," if job.get("tail_hold") else "")
    # voice_filter (opcional): leveling da voz, p.ex. acompressor, para fala com muita variacao de volume
    # (na Malu, "vai preparando o corpo" saia 20 dB abaixo do resto e a musica encobria)
    vf = job.get("voice_filter")
    f += (f"{vf}," if vf else "") + f"afade=t=in:d=0.05,afade=t=out:st={D - 0.35}:d=0.35[voice];"
    ins += f'-i "{W}/sfx_track.wav" '
    if SEP:
        f += (f"[{3 + len(BR)}:a]volume={job.get('sfx_db', -6)}dB,asplit[sfx][sxo];[voice]asplit[vc1][vc2];"
              f"[vc1][sfx]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[sc];"
              f"[vc2]alimiter=limit=0.95:level=false[ao];")
    else:
        f += (f"[{3 + len(BR)}:a]volume={job.get('sfx_db', -6)}dB[sfx];[voice][sfx]amix=inputs=2:duration=first:normalize=0,"
              f"alimiter=limit=0.95:level=false,asplit[ao][sc];")
    ins += f'-ss {MUSIC_OFFSET} -t {D + 1} -i "{MUS["file"]}" '
    f += (f"[{4 + len(BR)}:a]aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=35,volume={MUS.get('db', -20.5)}dB,"
          f"afade=t=in:d=0.3,afade=t=out:st={D - 0.6}:d=0.6[mus];"
          f"[mus][sc]sidechaincompress=threshold={job.get('duck_threshold', 0.03)}:ratio=4:attack=20:release=450:makeup=1[mo]")
    if FX:
        ins += f'-i "{W}/letter.mov" '
    if CAM:
        ins += f'-i "{W}/camera.mov" '
    return ins, f


if MODE == "prep":
    print("duracao", D, "trechos", SEGS, "\nreferencias", BR, "\nblocos", BLOCKS, "\nzooms", ZOOMS, "cortes", PUNCHES)
    if CAM:
        run(f'python3 "{MALU}/camera.py" "{job["_path"]}"')
    if KIN:
        run(f'python3 "{MALU}/kinetic/cli.py" "{job["_path"]}" all')
    elif FX:
        run(f'python3 "{SKILL}/scripts/fx_layer.py" "{job["_path"]}" {D} "{W}"')
    else:
        run(f'python3 "{SKILL}/scripts/caps_layer.py" "{job["captions"]}" {D} "{W}/caps.mov"')
    if job.get("burn_events"):              # Malu: film burn vermelho so nas trocas de layout (malu-cortes/scripts/burn.py)
        run(f'python3 "{MALU}/burn.py" "{job["_path"]}"')
    else:
        build_track()
    if job.get("sfx_engine") == "malu":      # biblioteca de SFX e cama de musica da Malu (malu-cortes/scripts/audio.py)
        run(f'python3 "{MALU}/audio.py" "{job["_path"]}"')
    else:
        build_sfx()
elif MODE == "check":
    # o ffmpeg as vezes trava no ENCERRAMENTO antecipado (-t 0.5) com este grafo: 0% de CPU e nunca sai
    # (visto 2x em 3 no reel da Malu, logo apos o prep). O grafo ja foi validado quando passa de 1 quadro;
    # timeout para nao ficar pendurado. O render completo nao usa -t antecipado e nao apresentou o problema.
    ins, f = graph()
    import signal
    pr = subprocess.Popen(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[vo]" -map "[ao]" -map "[mo]"{SXMAP} -t 0.5 -f null -',
                          shell=True, start_new_session=True)
    try:
        if pr.wait(timeout=120):
            sys.exit("check falhou")
    except subprocess.TimeoutExpired:
        os.killpg(pr.pid, signal.SIGKILL)
        print("AVISO: check travou no encerramento do ffmpeg (sem erro de grafo); siga para o render com vigia de CPU")
elif MODE == "preview":
    # python3 render.py job.json preview INICIO DURACAO -> <work>/preview_<inicio>.mp4 (1080x1920, audio mixado)
    # MP4 fragmentado: fica tocavel mesmo se o ffmpeg travar no encerramento antecipado (ver armadilhas).
    import signal
    t0p, durp = float(sys.argv[3]), float(sys.argv[4])
    ins, f = graph()
    outp = os.path.join(W, f"preview_{t0p:g}.mp4")
    f += (";[ao][mo][sxo]amix=inputs=3:duration=first:normalize=0[apv]" if SEP else
          ";[ao][mo]amix=inputs=2:duration=first:normalize=0[apv]")   # voz+SFX+musica numa faixa so
    pr = subprocess.Popen(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[vo]" -map "[apv]" -ss {t0p} -t {durp} '
                          f'-s 1080x1920 -c:v libx264 -preset fast -crf 17 -pix_fmt yuv420p -c:a aac -b:a 192k '
                          f'-movflags +frag_keyframe+empty_moov "{outp}"', shell=True, start_new_session=True)
    try:
        pr.wait(timeout=900)
    except subprocess.TimeoutExpired:
        os.killpg(pr.pid, signal.SIGKILL)
    print("preview:", outp)
elif MODE == "render":
    ins, f = graph()
    run(f'ffmpeg -v error -y {ins} -filter_complex "{f}" -map "[vo]" -map "[ao]" -map "[mo]"{SXMAP} -t {D} -c:v h264_videotoolbox '
        f'{AMETA}'
        f'-b:v {job.get("vbitrate", "45M")} -maxrate {job.get("vmaxrate", "60M")} -profile:v high -tag:v avc1 -color_range tv -colorspace bt709 -color_primaries bt709 '
        f'-color_trc bt709 -c:a aac -b:a 320k -movflags +faststart "{EDIT}"')
    # alvo de loudness (job["lufs"], p.ex. -16): mede a mistura e aplica o mesmo ganho nas duas faixas
    g = 0.0
    if job.get("lufs") is not None:
        r = subprocess.run(f'ffmpeg -hide_banner -nostats -i "{EDIT}" -filter_complex "{AMIX}'
                           f'duration=first:normalize=0,ebur128" -f null -', shell=True, capture_output=True, text=True).stderr
        i_lufs = float(r.split("Summary:")[1].split("I:")[1].split("LUFS")[0])
        g = round(job["lufs"] - i_lufs, 2)
        print("loudness", i_lufs, "LUFS -> ganho", g, "dB")
    run(f'ffmpeg -v error -y -i "{EDIT}" -filter_complex "{AMIX}duration=first:normalize=0,'
        f'volume={g}dB,alimiter=limit=0.84:level=false[a]" -map 0:v -map "[a]" -c:v copy {TAGS}-c:a aac -b:a 320k -movflags +faststart "{POST}"')
    if g:
        tmp = EDIT + ".tmp.mp4"
        run(f'ffmpeg -v error -y -i "{EDIT}" -map 0 -c:v copy {TAGS}-filter:a:0 "volume={g}dB,alimiter=limit=0.84:level=false" '
            f'-filter:a:1 "volume={g}dB" ' + (f'-filter:a:2 "volume={g}dB" ' if SEP else '') + f'-c:a aac -b:a 320k {AMETA}'
            f'-movflags +faststart "{tmp}" && mv "{tmp}" "{EDIT}"')
print("OK", MODE)
