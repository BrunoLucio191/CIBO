#!/usr/bin/env python3
"""Renderiza um corte vertical 9:16 do Dr. Energia BR Cast.

Faz: crop 9:16 com offset por corte, legenda queimada (Montserrat Bold branca
com contorno verde-escuro), marca d'agua da logo, capa estatica no inicio e
trilha musical com ducking sob a voz.
"""
import json
import os
import re
import subprocess
import sys

import os as _os
_AQUI = _os.path.dirname(_os.path.abspath(__file__))
ASSETS = _os.path.join(_os.path.dirname(_AQUI), "assets")
# RAIZ e a pasta do projeto do episodio; os assets vem da skill.
RAIZ = _os.environ.get("PROJETO", _os.getcwd())



FONTE_DIR = ASSETS
LOGO = _os.path.join(ASSETS, "logo_dr_energia.png")

W, H = 1080, 1920
# A capa e um frame unico: ela existe para ser a miniatura do feed, nao para
# segurar o comeco do video. Quem abre o corte e o burn-in verde.
CAPA_FRAMES = 1
# Burn-in: asset do acervo das skills (filmburn_blue.mp4), tingido de verde em
# 03_assets/filmburn_green.mp4. Ele fica preto ate 0,25s, estoura em 0,53s e
# some em 0,78s; por isso a copia de saida entra com o pico junto do fim.
BURN = _os.path.join(ASSETS, "filmburn_green.mp4")
BURN_PICO = 0.63        # quanto antes do fim o burn de saida comeca
# A gravacao esta marcada como 30 fps mas so tem ~23,7 fps de conteudo real:
# um frame a cada cinco e duplicado. Entregar a 24 conforma a cadencia de
# verdade em vez de carregar a duplicacao para dentro do corte.
FPS = 24
CAPA_SEG = CAPA_FRAMES / FPS
MAX_PALAVRAS = 4        # convencao do cliente: 2-4 palavras por legenda
MAX_CARACT = 22         # a politica da caption-quality-gate quer <=18, >24 alerta
MIN_BLOCO = 0.45        # s: abaixo disso a legenda pisca
MAX_CPS = 20.0          # caracteres por segundo confortaveis
MAX_FUNDIDO = 30        # ate aqui a legenda fundida ainda cabe em duas linhas
FORTE = (".", "?", "!")
FRACA = (",", ";", ":")


def hhmmss(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def grupos_legenda(palavras, ini, fim):
    """Agrupa palavras em blocos curtos, quebrando em pontuacao."""
    dentro = [p for p in palavras if p["end"] > ini and p["start"] < fim]
    grupos, atual = [], []
    for i, p in enumerate(dentro):
        atual.append(p)
        txt = " ".join(x["word"].strip() for x in atual)
        ultimo = p["word"].strip()
        # virgula so quebra se o bloco ja tem corpo, senao sobra fragmento solto
        quebra = (len(atual) >= MAX_PALAVRAS or len(txt) >= MAX_CARACT
                  or ultimo.endswith(FORTE)
                  or (ultimo.endswith(FRACA) and len(atual) >= 2))
        # nunca separar "ar" de "-condicionado": o transcritor quebra palavra
        # composta em dois tokens e a legenda fica comecando com hifen
        segue = dentro[i + 1]["word"].strip() if i + 1 < len(dentro) else ""
        if segue.startswith("-"):
            quebra = False
        if quebra:
            grupos.append(atual); atual = []
    if atual:
        grupos.append(atual)

    saida = []
    for g in grupos:
        t0 = max(g[0]["start"], ini) - ini
        t1 = min(g[-1]["end"], fim) - ini
        if t1 - t0 < 0.12:
            t1 = t0 + 0.12
        sobreposta = all(x.get("reparado") for x in g)
        txt = " ".join(x["word"].strip() for x in g).strip()
        txt = re.sub(r"\s+-", "-", txt)          # "ar -condicionado" -> "ar-condicionado"
        txt = txt.lstrip(",.;:!? ").strip()
        if txt:
            saida.append((t0, t1, txt, sobreposta))

    # elimina sobreposicao entre blocos vizinhos
    for i in range(len(saida) - 1):
        if saida[i][1] > saida[i + 1][0]:
            saida[i] = (saida[i][0], saida[i + 1][0], saida[i][2], saida[i][3])

    return arruma_ritmo(saida, fim - ini)


def arruma_ritmo(blocos, dur_total):
    """Deixa cada legenda legivel: sem piscar, sem correr e sem palavra partida.

    Tres defeitos aparecem no render e nenhum e visivel no texto solto. Um
    bloco de uma palavra com 0,15 s chega a 60 caracteres por segundo e vira
    flash. Um bloco que comeca com hifen e metade de uma palavra composta que
    caiu no bloco anterior ("ar" / "-condicionado"). E um bloco pode acabar
    depois do comeco do proximo, quando os dois interlocutores falam juntos.

    A ordem de tentativa importa: esticar para dentro do silencio e de graca;
    pedir tempo emprestado ao vizinho so custa se ele tambem estiver apertado;
    fundir e o ultimo recurso, porque engorda a linha.
    """
    b = [list(x) for x in blocos]        # (ini, fim, texto, veio_de_fala_sobreposta)

    # 1) palavra composta partida volta para o bloco anterior
    i = 1
    while i < len(b):
        if b[i][2].startswith("-") and len(b[i - 1][2] + b[i][2]) <= MAX_CARACT + 12:
            b[i - 1][2] = b[i - 1][2] + b[i][2]
            b[i - 1][1] = max(b[i - 1][1], b[i][1])
            b.pop(i)
            continue
        i += 1

    def precisa(txt):
        return max(MIN_BLOCO, len(txt) / MAX_CPS)

    # 1b) fala sobreposta: quando os dois falam por cima dizendo quase a mesma
    # coisa, o alinhador devolve duas frases quase iguais e sem tempo entre
    # elas. Nao cabe legendar as duas; fica a que tem tempo para ser lida.
    i = 0
    while i < len(b) - 1:
        a_tok = set(b[i][2].lower().split())
        c_tok = set(b[i + 1][2].lower().split())
        comum = len(a_tok & c_tok) / max(len(a_tok | c_tok), 1)
        if comum >= 0.5 and (b[i][3] or b[i + 1][3]):
            dur_a = b[i][1] - b[i][0]
            dur_c = b[i + 1][1] - b[i + 1][0]
            aperto_a = dur_a / precisa(b[i][2])
            aperto_c = dur_c / precisa(b[i + 1][2])
            if min(aperto_a, aperto_c) < 0.6:
                fora = i if aperto_a < aperto_c else i + 1
                fica = i + 1 if fora == i else i
                b[fica][0] = min(b[fica][0], b[fora][0])
                b[fica][1] = max(b[fica][1], b[fora][1])
                b.pop(fora)
                continue
        i += 1

    # 2) ritmo, do fim para o comeco para que o emprestimo nao se propague
    for _ in range(3):
        for i in range(len(b) - 1, -1, -1):
            t0, t1, txt = b[i][0], b[i][1], b[i][2]
            alvo = precisa(txt)
            if t1 - t0 >= alvo - 1e-3:
                continue
            teto = b[i + 1][0] if i + 1 < len(b) else dur_total
            b[i][1] = t1 = min(teto, t0 + alvo)      # silencio depois do bloco
            if t1 - t0 >= alvo - 1e-3:
                continue
            if i + 1 < len(b):                        # emprestimo do vizinho
                p0, p1, ptxt = b[i + 1][0], b[i + 1][1], b[i + 1][2]
                sobra = (p1 - p0) - precisa(ptxt)
                if sobra > 0.02:
                    delta = min(sobra, alvo - (t1 - t0))
                    b[i + 1][0] = p0 + delta
                    b[i][1] = t1 = t1 + delta
            if i > 0 and t1 - t0 < alvo - 1e-3:       # emprestimo do anterior
                a0, a1, atxt = b[i - 1][0], b[i - 1][1], b[i - 1][2]
                sobra = (a1 - a0) - precisa(atxt)
                if sobra > 0.02:
                    delta = min(sobra, alvo - (t1 - t0))
                    b[i - 1][1] = a1 - delta
                    b[i][0] = t0 = t0 - delta
            if t1 - t0 >= alvo - 1e-3 or i == 0:
                continue
            junto = b[i - 1][2] + " " + txt           # fundir com o anterior
            if len(junto) <= MAX_FUNDIDO:
                b[i - 1] = [b[i - 1][0], max(b[i - 1][1], t1), junto, b[i - 1][3]]
                b.pop(i)
                continue
            if i + 1 < len(b):                        # ou com o seguinte
                junto = txt + " " + b[i + 1][2]
                if len(junto) <= MAX_FUNDIDO:
                    b[i] = [t0, max(t1, b[i + 1][1]), junto, b[i][3]]
                    b.pop(i + 1)

    # 3) nenhum bloco invade o proximo nem nasce invertido
    limpo = []
    for i, (t0, t1, txt, _sobre) in enumerate(b):
        teto = b[i + 1][0] if i + 1 < len(b) else dur_total
        t1 = min(t1, teto)
        if not txt.strip():
            continue
        if t1 - t0 < 0.10:
            # Bloco sem tempo nao pode ser descartado: sumir com a fala e pior
            # que uma legenda apertada. O texto vai para o vizinho.
            if limpo:
                ant0, ant1, ant = limpo[-1][0], limpo[-1][1], limpo[-1][2]
                limpo[-1] = (ant0, max(ant1, t1), ant + " " + txt)
            elif i + 1 < len(b):
                b[i + 1][0] = min(b[i + 1][0], t0)
                b[i + 1][2] = txt + " " + b[i + 1][2]
            continue
        limpo.append((round(t0, 3), round(t1, 3), txt))
    return limpo


def escreve_ass(grupos, caminho):
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Corte,Montserrat,105,&H00FFFFFF,&H00FFFFFF,&H0005530A,&H64000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    linhas = [f"Dialogue: 0,{hhmmss(g[0])},{hhmmss(g[1])},Corte,,0,0,0,,{g[2]}"
              for g in grupos]
    open(caminho, "w").write(cab + "\n".join(linhas) + "\n")


def ganho_para_alvo(cmd_base, filtro, rotulo, alvo=-15.0):
    """Mede um stream do grafo e devolve o ganho fixo que o leva ao alvo, em dB.

    Nada aqui usa loudnorm dinamico. O loudnorm nivela trecho a trecho: na voz
    ele levanta o ruido de sala das pausas quase ate o nivel da fala, e no mix
    ele levanta a trilha onde nao ha voz. Medir uma vez e aplicar um ganho fixo
    preserva a dinamica original e a distancia entre voz e cama.
    """
    # o ebur128 entra dentro do proprio grafo: -af nao pode ser combinado com
    # uma saida de -filter_complex, e essa combinacao falha em silencio
    graf = f"{filtro};{rotulo}ebur128=peak=none[med]"
    r = subprocess.run(cmd_base + ["-filter_complex", graf,
                                   "-map", "[med]", "-f", "null", "-"],
                       capture_output=True, text=True)
    achados = re.findall(r"I:\s*(-?[0-9.]+) LUFS", r.stderr)
    if not achados:
        raise RuntimeError(f"nao consegui medir {rotulo}: {r.stderr[-600:]}")
    return max(-12.0, min(12.0, alvo - float(achados[-1])))


def render(cfg, palavras):
    ini, fim = cfg["ini"], cfg["fim"]
    dur = fim - ini
    nome = cfg["nome"]
    tmp = f"{RAIZ}/04_trabalho/tmp"
    os.makedirs(tmp, exist_ok=True)

    ass = f"{tmp}/{nome}.ass"
    escreve_ass(grupos_legenda(palavras, ini, fim), ass)

    sendcmd = f"{tmp}/{nome}.sendcmd"
    if not os.path.exists(sendcmd):
        subprocess.run([sys.executable, f"{RAIZ}/04_trabalho/reframe.py",
                        f"{RAIZ}/{cfg['fonte']}", str(ini), str(fim), sendcmd],
                       check=True)

    capa = cfg.get("capa") or f"{RAIZ}/04_trabalho/capas/{nome}.png"
    musica = cfg["musica"]
    if not musica.startswith("/"):
        musica = _os.path.join(ASSETS, "music", musica)
    off = cfg.get("musica_offset", 0)
    # As faixas foram equalizadas para -26 dB relativos (ver decisao_musical.md).
    # Isso e o default da podcast-reels, mas neste material ainda ficou alto:
    # -4 dB colocam a cama em -30 dB, uns 11 dB abaixo da voz.
    ganho = cfg.get("musica_gain", 0.16) * 0.63
    cx = cfg.get("crop_x", 0.5)      # 0=esquerda, 1=direita do frame 1920
    total = dur + CAPA_SEG

    largura_crop = round(H_ratio := 1080 * 9 / 16)  # 607.5 -> 608
    largura_crop = 608
    xmax = 1920 - largura_crop
    xoff = round(cx * xmax)

    filtro = (
        # v0: video do corte, crop 9:16 -> 1080x1920, legenda queimada
        f"[0:v]fps={FPS},sendcmd=f='{sendcmd}',crop={largura_crop}:1080:{xoff}:0,"
        f"scale={W}:{H}:flags=lanczos,"
        f"setsar=1,eq=contrast=1.04:saturation=1.06,"
        f"subtitles='{ass}':fontsdir='{FONTE_DIR}'[vc];"
        # logo marca d'agua
        f"[2:v]scale=250:-1[lg];"
        f"[vc][lg]overlay=(W-w)/2:H-h-70,format=gbrp[vw];"
        # burn-in verde na entrada e na saida, do asset do acervo. O tpad
        # estende cada copia com preto, que em screen e neutro, para as duas
        # caberem na duracao do corte sem cortar o video.
        f"[4:v]fps={FPS},scale={W}:{H},setsar=1,split=2[fbA][fbB];"
        f"[fbA]tpad=stop_mode=add:stop_duration=120:color=black,format=gbrp[fb1];"
        f"[fbB]tpad=start_mode=add:start_duration={max(dur-BURN_PICO,0):.3f}:color=black,"
        f"tpad=stop_mode=add:stop_duration=120:color=black,format=gbrp[fb2];"
        # o screen precisa acontecer em RGB: em YUV ele tambem soma os planos
        # de croma, e o verde vira magenta na tela inteira
        f"[vw][fb1]blend=all_mode=screen:shortest=1[vb1];"
        f"[vb1][fb2]blend=all_mode=screen:shortest=1,format=yuv420p[vb];"
        # capa: um frame so, sem fade, so para o feed ter miniatura
        f"[1:v]scale={W}:{H},setsar=1,loop=loop=-1:size=1:start=0,"
        f"trim=duration={CAPA_SEG:.4f}[cap];"
        f"[cap][vb]concat=n=2:v=1:a=0[vout];"
    )

    # O audio e montado primeiro sozinho, medido, e so entao o corte inteiro e
    # renderizado com o ganho fixo que o leva a -15 LUFS.
    def voz_crua():
        return (f"[0:a]atrim=0:{dur},asetpts=PTS-STARTPTS,"
                f"adelay={int(CAPA_SEG*1000)}|{int(CAPA_SEG*1000)},"
                f"highpass=f=80[vozcrua]")

    def filtro_audio(g, gv):
        return (
            f"[0:a]atrim=0:{dur},asetpts=PTS-STARTPTS,"
            f"adelay={int(CAPA_SEG*1000)}|{int(CAPA_SEG*1000)},"
            f"highpass=f=80,volume={gv:.2f}dB,asplit=2[voz][key];"
            f"[3:a]atrim={off}:{off+total},asetpts=PTS-STARTPTS,"
            f"volume={ganho},afade=t=in:st=0:d=0.9,"
            f"afade=t=out:st={total-1.2}:d=1.2[mus];"
            f"[mus][key]sidechaincompress=threshold=0.06:ratio=9:attack=25:"
            f"release=380:makeup=1[musd];"
            f"[voz][musd]amix=inputs=2:duration=first:normalize=0,"
            f"volume={g:.2f}dB,"
            # level=disabled: com o auto-level ligado o alimiter reempurra o
            # mix ate o teto e o pico real volta a passar de -1 dBTP
            f"alimiter=limit=0.79:level=disabled[aout]"
        )

    entradas = [
        "-ss", str(ini), "-t", str(dur), "-i", f"{RAIZ}/{cfg['fonte']}",
        "-loop", "1", "-t", str(CAPA_SEG), "-i", capa,
        "-i", LOGO,
        "-i", musica,
        "-i", BURN,
    ]
    medir = ["ffmpeg", "-v", "info", "-nostats"] + entradas
    ganho_voz = ganho_para_alvo(medir, voz_crua(), "[vozcrua]")
    ganho_mix = ganho_para_alvo(medir, filtro_audio(0.0, ganho_voz), "[aout]")
    filtro = filtro + filtro_audio(ganho_mix, ganho_voz)
    print(f"   voz {ganho_voz:+.1f} dB | mix {ganho_mix:+.1f} dB")


    saida = f"{RAIZ}/06_entrega/{nome}.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-stats",
        *entradas,
        "-filter_complex", filtro,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "h264_videotoolbox", "-b:v", "12M", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        # sinalizacao de cor completa: sem isso o player adivinha e a cor escorrega
        "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-color_range", "tv",
        # o h264_videotoolbox descarta trc/primaries; o bsf grava na VUI do SPS
        "-bsf:v", ("h264_metadata=video_full_range_flag=0:colour_primaries=1"
                   ":transfer_characteristics=1:matrix_coefficients=1"),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", saida,
    ]
    print("->", nome)
    subprocess.run(cmd, check=True)
    return saida


if __name__ == "__main__":
    cfgs = json.load(open(sys.argv[1]))
    palavras = json.load(open(sys.argv[2]))
    alvos = sys.argv[3:]
    for c in cfgs:
        if alvos and c["nome"] not in alvos:
            continue
        render(c, palavras)
