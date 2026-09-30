"""Ataque e fim de fala no envelope do audio editado (compartilhado por sync_captions e review_job).

O tempo de palavra do Whisper oscila 0,1-0,6 s. A verdade e o envelope (quadros de 10 ms, limiar -40 dB).
Casos reais do reel da Malu que definiram as regras:
- "bolinha | entao": o Whisper cola o inicio de "entao" na cauda de "bolinha" e engole a pausa de 350 ms;
- "toxina": o /ʃ/ fica 180 ms abaixo de -40 dB e NAO e pausa (por isso o minimo de 250 ms);
- "intoxicada": o Whisper termina a palavra em 12,74, mas o "-da" vai ate 13,35 (depois da oclusiva do "d");
- buscar ataque para tras do tempo do Whisper puxava "saiu" para o "-gado" de "figado": nunca fazer isso.
"""
import subprocess
import numpy as np

SR, H = 16000, 160


def edited_envelope(audio, segs):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", audio, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    y = np.frombuffer(raw, np.float32)
    ed = np.concatenate([y[int(s0 * SR):int(s1 * SR)] for s0, s1 in segs])
    n = len(ed) // H
    return 20 * np.log10(np.sqrt((ed[:n * H].reshape(n, H) ** 2).mean(1)) + 1e-9)


def is_onset(env, i, gap=6):
    """Silencio -> voz SUSTENTADA (5 de 8 quadros acima de -40 dB ou pico > -30 dB). Um residuo de 40 ms (respiracao,
    cauda de "grossa") depois da pausa virava "ataque" e a legenda entrava 0,3 s antes de "Primeiro"."""
    # calibrado nos dois casos reais: residuo 43,44 (3 quadros, pico -33) nao e ataque; "se" 13,38 (5 quadros, pico -30) e.
    return (env[i] > -40 and (env[max(0, i - gap):i] < -40).all()
            and ((env[i:i + 8] > -40).sum() >= 5 or env[i:i + 10].max() > -30))


def onset(env, ws, we):
    """Ataque real de uma palavra que o Whisper marcou em [ws, we] (tempo do video)."""
    n = len(env); i0, i1 = int(ws * 100), min(len(env), int((we + 0.1) * 100))
    near = [i for i in range(max(6, i0 - 15), min(n, i0 + 16)) if is_onset(env, i)]
    if near:                                         # ataque colado no tempo do Whisper
        return min(near, key=lambda i: abs(i - i0)) / 100
    if i0 < n and env[i0:i0 + 8].mean() < -40:      # Whisper em silencio: primeiro ataque dentro da palavra
        return next((i / 100 for i in range(i0, i1) if is_onset(env, i)), None)
    # Whisper na cauda da palavra anterior: primeiro ataque depois de silencio >= 250 ms
    return next((i / 100 for i in range(i0 + 25, i1) if is_onset(env, i, 25)), None)


def offset(env, we, limit):
    """Fim real da fala que continua depois de we: primeiro silencio >= 150 ms (ate limit)."""
    n = len(env); i = int(we * 100)
    while i < min(n, int(limit * 100)):
        if (env[i:i + 15] < -40).all():
            return i / 100
        i += 1
    return min(limit, n / 100)


def _nrm(s):
    import re, unicodedata
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.findall(r"[a-z0-9]+", s)


def align(caps, W):
    """Primeira e ultima palavra do Whisper (indices em W) de cada bloco, por alinhamento texto x transcricao.
    Revisor e sincronizador PRECISAM usar o mesmo alinhamento: com janela de tempo o revisor pegava a ultima
    palavra do bloco anterior e acusava atraso que nao existia."""
    import difflib
    tt, tw, ct, cc = [], [], [], []
    for i, w in enumerate(W):
        for t in _nrm(w["word"]): tt.append(t); tw.append(i)
    for i, c in enumerate(caps):
        for t in _nrm(c["text"]): ct.append(t); cc.append(i)
    first, last = {}, {}
    for blk in difflib.SequenceMatcher(None, ct, tt, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            ci, wi = cc[blk.a + k], tw[blk.b + k]
            first.setdefault(ci, wi); last[ci] = wi
    return first, last
