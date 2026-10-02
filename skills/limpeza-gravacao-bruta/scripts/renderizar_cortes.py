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

f, c = [], ""
for i, (x, y) in enumerate(keep):
    d = y - x
    f.append(f"[0:v]trim={x:.3f}:{y:.3f},setpts=PTS-STARTPTS[v{i}]")
    f.append(f"[0:a]atrim={x:.3f}:{y:.3f},asetpts=PTS-STARTPTS,"
             f"afade=t=in:d=0.015,afade=t=out:st={max(0, d - 0.02):.3f}:d=0.02[a{i}]")
    c += f"[v{i}][a{i}]"
# fade-in/fade-out pedidos para o episódio inteiro (Bombordo EP 04): só nas pontas, nunca nas emendas
vf, af = [], []
if a.fade_in > 0:
    vf.append(f"fade=t=in:st=0:d={a.fade_in:.3f}"); af.append(f"afade=t=in:st=0:d={a.fade_in:.3f}")
if a.fade_out > 0:
    st = max(0.0, total - a.fade_out)
    vf.append(f"fade=t=out:st={st:.3f}:d={a.fade_out:.3f}"); af.append(f"afade=t=out:st={st:.3f}:d={a.fade_out:.3f}")
f.append(c + f"concat=n={len(keep)}:v=1:a=1[vc][ac]")
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
