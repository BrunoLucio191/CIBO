#!/usr/bin/env python3
"""Transcreve em lote gravações longas (aulas, lives, cursos) com mlx-whisper, em série e retomável.

Rodar com o python do mlx-whisper:
  ~/.local/share/uv/tools/mlx-whisper/bin/python transcrever_lote.py SAIDA ARQ1 [ARQ2 ...] [opções]
  (ARQ pode ser uma pasta: pega os vídeos/áudios de dentro, em ordem de nome)

Opções:
  --modo rapido|normal|qualidade   rapido = turbo com áudio a 1,3x (Pós 5: ~15 min por 9 h de aula);
                                   normal = turbo em velocidade normal (padrão);
                                   qualidade = large-v3 completo (lento; ~3 GB de modelo)
  --glossario "termo1, termo2"     nomes e termos técnicos do curso (vai como initial_prompt)
  --tmp PASTA                      temporários (padrão: SAIDA/_tmp, no SSD; nunca no disco de sistema)
  --nome NOME                      nome de saída quando há um arquivo só

O que faz (herdado do pipeline da Pós 5 do IFB, set/2026):
- tira silêncios longos (>= 20 s: intervalo, almoço, sala vazia) antes de transcrever e marca
  onde estavam, então 9 h de gravação viram ~7 h de fala;
- quebra em blocos de até 20 min cortados numa pausa curta (nunca no meio de palavra);
- guarda cada bloco pronto (cache): se parar (RAM, SSD desconectado, "pausa aí"), ao rodar de
  novo continua de onde parou;
- UM arquivo e UM modelo por vez: dois whisper grandes em paralelo esgotaram os 16 GB;
- escreve progresso com previsão de término em SAIDA/progresso.log.
Saída: SAIDA/<nome>.json com segments no tempo ORIGINAL da gravação e a lista de pausas.
Depois rode formatar.py para gerar TXT com [hh:mm:ss] e SRT.
"""
import argparse, json, re, shutil, subprocess, time
from pathlib import Path

MODELOS = {"rapido": "mlx-community/whisper-large-v3-turbo", "normal": "mlx-community/whisper-large-v3-turbo",
           "qualidade": "mlx-community/whisper-large-v3-mlx"}
EXT = {".mp4", ".mov", ".mkv", ".m4a", ".mp3", ".wav", ".opus", ".flac", ".aac", ".webm", ".m4v"}
SIL_LONGO, BLOCO_MAX = 20.0, 20 * 60.0

ap = argparse.ArgumentParser()
ap.add_argument("saida")
ap.add_argument("arquivos", nargs="+")
ap.add_argument("--modo", choices=MODELOS, default="normal")
ap.add_argument("--glossario", default="")
ap.add_argument("--tmp")
ap.add_argument("--nome")
a = ap.parse_args()
OUT = Path(a.saida); OUT.mkdir(parents=True, exist_ok=True)
TMP = Path(a.tmp) if a.tmp else OUT / "_tmp"
LOG = OUT / "progresso.log"
TEMPO = 1.3 if a.modo == "rapido" else 1.0


def log(msg):
    linha = f"{time.strftime('%d/%m %H:%M')} {msg}"
    print(linha, flush=True)
    with open(LOG, "a") as f:
        f.write(linha + "\n")


def silencios(wav, d, n):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(wav), "-af", f"silencedetect=n={n}dB:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    ini = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    fim = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    return list(zip(ini, fim + [None] * (len(ini) - len(fim))))


def preparar(src, pasta):
    """Extrai o áudio, acha as regiões com fala e os pontos de corte dos blocos."""
    man = pasta / "manifesto.json"
    if man.exists():
        return json.loads(man.read_text())
    pasta.mkdir(parents=True, exist_ok=True)
    wav = pasta / "full.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                               capture_output=True, text=True).stdout)
    regioes, pausas, cur = [], [], 0.0
    for x, y in silencios(wav, SIL_LONGO, -45):
        y = dur if y is None else y
        pausas.append([round(x, 2), round(y, 2)])
        if x + 1 > cur:
            regioes.append((cur, x + 1))
        cur = max(cur, y - 1)
    if cur < dur:
        regioes.append((cur, dur))
    curtas = [(x + y) / 2 for x, y in silencios(wav, 0.4, -35) if y]
    blocos = []
    for x, y in regioes:
        while y - x > BLOCO_MAX:
            cand = [c for c in curtas if x + BLOCO_MAX * 0.8 < c <= x + BLOCO_MAX]
            corte = cand[-1] if cand else x + BLOCO_MAX
            blocos.append((x, corte)); x = corte
        if y - x > 2:
            blocos.append((x, y))
    m = {"duracao": dur, "pausas": pausas, "blocos": [{"inicio": x, "fim": y} for x, y in blocos]}
    man.write_text(json.dumps(m))
    return m


def transcrever(src, nome):
    import mlx_whisper
    pasta = TMP / re.sub(r"[^\w.-]", "_", nome)
    m = preparar(src, pasta)
    wav = pasta / "full.wav"
    fala = sum(b["fim"] - b["inicio"] for b in m["blocos"])
    log(f"inicio {nome}: {m['duracao']/3600:.1f} h de gravação, {fala/3600:.1f} h de fala, {len(m['blocos'])} blocos")
    t0, feito, segs = time.time(), 0.0, []
    for i, b in enumerate(m["blocos"]):
        parcial = pasta / f"b{i:03d}.json"
        if parcial.exists():
            r = json.loads(parcial.read_text())
        else:
            w = pasta / f"b{i:03d}.wav"
            filtro = ["-af", f"atempo={TEMPO}"] if TEMPO != 1.0 else []
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{b['inicio']:.3f}", "-to", f"{b['fim']:.3f}",
                            "-i", str(wav), *filtro, "-ac", "1", "-ar", "16000", str(w)], check=True)
            res = mlx_whisper.transcribe(str(w), path_or_hf_repo=MODELOS[a.modo], language="pt",
                                         condition_on_previous_text=False, verbose=None,
                                         initial_prompt=a.glossario or None)
            r = {"segments": [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in res["segments"]]}
            parcial.write_text(json.dumps(r, ensure_ascii=False))
            w.unlink()
            feito += b["fim"] - b["inicio"]
            falta_fala = sum(bb["fim"] - bb["inicio"] for bb in m["blocos"][i + 1:])
            resta = (time.time() - t0) / feito * falta_fala
            log(f"  {nome}: bloco {i + 1}/{len(m['blocos'])}, faltam ~{resta/60:.0f} min neste arquivo")
        segs += [{"start": round(b["inicio"] + s["start"] * TEMPO, 2),
                  "end": round(min(b["fim"], b["inicio"] + s["end"] * TEMPO), 2), "text": s["text"]}
                 for s in r["segments"]]
    (OUT / f"{nome}.json").write_text(json.dumps(
        {"arquivo": str(src), "duracao_original": m["duracao"], "pausas": m["pausas"], "segments": segs,
         "text": "".join(s["text"] for s in segs), "modelo": MODELOS[a.modo], "tempo": TEMPO}, ensure_ascii=False))
    shutil.rmtree(pasta, ignore_errors=True)  # cache só serve enquanto o arquivo não termina
    log(f"fim {nome} ({(time.time() - t0)/60:.0f} min)")


fila = []
for arq in map(Path, a.arquivos):
    fila += sorted(p for p in arq.iterdir() if p.suffix.lower() in EXT) if arq.is_dir() else [arq]
if a.nome and len(fila) != 1:
    raise SystemExit("--nome só vale com um arquivo")
for src in fila:
    nome = a.nome or src.stem
    if (OUT / f"{nome}.json").exists():
        log(f"pula {nome} (já transcrito)")
        continue
    try:
        transcrever(src, nome)
    except Exception as e:  # segue a fila; o cache deixa retomar esse arquivo depois
        log(f"FALHOU {nome}: {e}")
if TMP.exists() and not any(TMP.iterdir()):
    TMP.rmdir()
log("TUDO_PRONTO")
