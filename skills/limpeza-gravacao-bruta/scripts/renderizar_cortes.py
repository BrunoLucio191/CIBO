#!/usr/bin/env python3
"""Renderiza o original sem os trechos cortados, verifica e só então substitui a saída.

Uso:
  python3 renderizar_cortes.py ORIGINAL cortes.json SAIDA.mp4 [--bitrate 8M] [--so-plano]

cortes.json: [[inicio, fim], ...] em segundos do original (null = até o final).

- Corta por frame com trim/atrim + concat (stream copy cortaria no keyframe).
- Fade de áudio de 15–20 ms em cada emenda (sem estalo, sem comer sílaba).
- Encoder: h264_videotoolbox no Mac (~6x tempo real em 1080p30), libx264 fora dele.
  Bitrate: um pouco acima do original (gravação OBS ~6 Mb/s → 8 Mb/s).
- Renderiza num arquivo temporário, decodifica o arquivo INTEIRO e só substitui
  SAIDA se não houver nenhum erro. Um render interrompido já gerou AAC corrompido
  (1.943 erros) que parecia normal no ffprobe.
- Imprime a posição de cada emenda no vídeo final (para o usuário conferir).
"""
import argparse, json, os, platform, subprocess, sys, tempfile

ap = argparse.ArgumentParser()
ap.add_argument("original")
ap.add_argument("cortes")
ap.add_argument("saida")
ap.add_argument("--bitrate", default="8M")
ap.add_argument("--so-plano", action="store_true", help="só imprime as emendas, sem renderizar")
ap.add_argument("--fade-in", type=float, default=0.0, help="fade do preto + áudio no começo do episódio (s)")
ap.add_argument("--fade-out", type=float, default=0.0, help="fade para o preto + áudio no fim do episódio (s)")
ap.add_argument("--punch", help="JSON [[ini, fim, zoom, cx, cy], ...] em segundos do ORIGINAL: zoom (punch-in) "
                "para disfarçar emenda no mesmo plano; cx/cy = centro do zoom (0–1)")
a = ap.parse_args()

cortes = sorted(json.load(open(a.cortes)), key=lambda c: c[0])
keep, t = [], 0.0
for ini, fim in cortes:
    if ini > t:
        keep.append((t, ini))
    t = fim if fim is not None else float("inf")
if t != float("inf"):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                a.original], capture_output=True, text=True).stdout)
    if dur > t:
        keep.append((t, dur))

acc, emendas = 0.0, []
for x, y in keep[:-1]:
    acc += y - x
    emendas.append(acc)
total = sum(y - x for x, y in keep)
print("emendas no vídeo final:", "  ".join(f"{int(e // 60)}:{e % 60:05.2f}" for e in emendas))
print(f"duração final: {int(total // 60)}min{total % 60:02.0f}s")
if a.so_plano:
    sys.exit()

# Punch-in (Katia, podcast multicâmera 14/09): emenda que não cai numa troca de câmera vira jump cut no mesmo
# plano. O trecho depois dela entra com zoom até a próxima troca de câmera, e a emenda passa por troca de plano.
punch = json.load(open(a.punch)) if a.punch else []
W0, H0, fr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                             "stream=width,height,r_frame_rate", "-of", "csv=p=0", a.original],
                            capture_output=True, text=True).stdout.strip().split(",")[:3]
W0, H0 = int(W0), int(H0)
# A troca de câmera medida é o PTS do primeiro quadro do plano novo; trim até esse tempo (arredondado para cima)
# leva esse quadro com o zoom do plano anterior (frame solto, Katia 20:29). Recua as bordas meio quadro.
num, den = (fr.split("/") + ["1"])[:2]
meio = 0.5 * float(den) / float(num)
punch = [[p[0] - meio, p[1] - meio, *p[2:]] for p in punch]


def pedacos(x, y):
    """Divide [x, y] nas bordas dos punch-ins: [(ini, fim, punch|None)]."""
    # borda a menos de um quadro da ponta do trecho geraria um pedaço de 0–1 quadro (frame solto)
    bordas = sorted({x, y, *(t for p in punch for t in p[:2] if x + 2 * meio < t < y - 2 * meio)})
    out = []
    for u, v in zip(bordas, bordas[1:]):
        p = next((p for p in punch if p[0] <= (u + v) / 2 <= p[1]), None)
        out.append((u, v, p))
    return out


f, cv, ca, nv = [], "", "", 0
for i, (x, y) in enumerate(keep):
    d = y - x
    for u, v, p in pedacos(x, y):
        z = ""
        if p:
            zoom, cx, cy = p[2:5]
            cw, ch = round(W0 / zoom / 2) * 2, round(H0 / zoom / 2) * 2
            ox = min(max(0, round(cx * W0 - cw / 2)), W0 - cw)
            oy = min(max(0, round(cy * H0 - ch / 2)), H0 - ch)
            z = f",crop={cw}:{ch}:{ox}:{oy},scale={W0}:{H0}:flags=lanczos,setsar=1"
        f.append(f"[0:v]trim={u:.3f}:{v:.3f},setpts=PTS-STARTPTS{z}[v{nv}]")
        cv += f"[v{nv}]"
        nv += 1
    f.append(f"[0:a]atrim={x:.3f}:{y:.3f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:d=0.015,afade=t=out:st={max(0, d - 0.02):.3f}:d=0.02[a{i}]")
    ca += f"[a{i}]"
# fade-in/fade-out pedidos para o episódio inteiro (Bombordo EP 04): só nas pontas, nunca nas emendas
vf, af = [], []
if a.fade_in > 0:
    vf.append(f"fade=t=in:st=0:d={a.fade_in:.3f}"); af.append(f"afade=t=in:st=0:d={a.fade_in:.3f}")
if a.fade_out > 0:
    st = max(0.0, total - a.fade_out)
    vf.append(f"fade=t=out:st={st:.3f}:d={a.fade_out:.3f}"); af.append(f"afade=t=out:st={st:.3f}:d={a.fade_out:.3f}")
f.append(cv + f"concat=n={nv}:v=1:a=0[vc]")
f.append(ca + f"concat=n={len(keep)}:v=0:a=1[ac]")
f.append(f"[vc]{','.join(vf) or 'null'}[v]")
f.append(f"[ac]{','.join(af) or 'anull'}[a]")
fc = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
fc.write(";".join(f))
fc.close()

venc = (["-c:v", "h264_videotoolbox", "-b:v", a.bitrate, "-maxrate", "12M", "-profile:v", "high"]
        if platform.system() == "Darwin" else ["-c:v", "libx264", "-preset", "fast", "-crf", "18"])
tmp = os.path.join(os.path.dirname(os.path.abspath(a.saida)), "_tmp_render_" + os.path.basename(a.saida))
# FFmpeg 7+/8: -/filter_complex ARQUIVO (a opção -filter_complex_script foi removida)
cmd = ["ffmpeg", "-v", "error", "-stats", "-y", "-i", a.original, "-/filter_complex", fc.name,
       "-map", "[v]", "-map", "[a]", *venc, "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", tmp]
if subprocess.run(cmd).returncode != 0:
    sys.exit("render falhou")

def duracoes(arq):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration", "-of", "csv=p=0", arq],
                         capture_output=True, text=True).stdout
    return {t: float(d) for t, d in (l.split(",")[:2] for l in out.splitlines() if "," in l) if d not in ("", "N/A")}


# Episódio de ~1 h (Autismo Cast, 18/09): vários atrim da mesma entrada num grafo só geraram 59:56 de vídeo
# e 4:17 de áudio, com exit 0 e decodificação limpa. Confere as duas trilhas contra o total esperado e, se
# o áudio encurtou, refaz só o áudio a partir de um WAV (corte exato por amostra) e remuxa o vídeo sem re-encode.
d = duracoes(tmp)
if abs(d.get("video", 0) - total) > 0.3:
    sys.exit(f"VÍDEO COM DURAÇÃO ERRADA: {d.get('video')} s, esperado {total:.2f} s. Mantido em {tmp}.")
if abs(d.get("audio", 0) - total) > 0.3:
    print(f"áudio com {d.get('audio')} s (esperado {total:.2f} s): refazendo o áudio a partir de WAV…")
    wav = tmp + ".full.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.original, "-vn", "-c:a", "pcm_s16le", wav], check=True)
    partes = []
    for i, (x, y) in enumerate(keep):
        p = f"{tmp}.a{i:03d}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{x:.3f}", "-t", f"{y - x:.3f}", "-i", wav,
                        "-af", f"afade=t=in:d=0.015,afade=t=out:st={max(0, y - x - 0.02):.3f}:d=0.02", p], check=True)
        partes.append(p)
    lista = tmp + ".lista.txt"
    open(lista, "w").write("".join(f"file '{p}'\n" for p in partes))
    fixo = tmp + ".fix.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-f", "concat", "-safe", "0", "-i", lista,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", *(["-af", ",".join(af)] if af else []),
                    "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", fixo], check=True)
    for p in partes + [wav, lista]:
        os.remove(p)
    os.replace(fixo, tmp)
    d = duracoes(tmp)
    if abs(d.get("audio", 0) - total) > 0.3:
        sys.exit(f"ÁUDIO AINDA COM DURAÇÃO ERRADA: {d.get('audio')} s, esperado {total:.2f} s. Mantido em {tmp}.")
print(f"durações ok: vídeo {d['video']:.2f} s, áudio {d['audio']:.2f} s (esperado {total:.2f} s)")

print("decodificando o arquivo inteiro para checar integridade…")
err = subprocess.run(["ffmpeg", "-v", "error", "-i", tmp, "-f", "null", "-"], capture_output=True, text=True).stderr
n = len([l for l in err.splitlines() if l.strip()])
if n:
    sys.exit(f"ARQUIVO COM ERRO ({n} linhas de erro). Mantido em {tmp}; SAIDA não foi substituída.\n{err[:500]}")
os.replace(tmp, a.saida)
print(f"ok: {a.saida} (0 erros de decodificação)")
