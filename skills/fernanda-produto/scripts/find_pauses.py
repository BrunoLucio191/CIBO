"""Mede pausas reais da fala pelo envelope do audio.

Uso:
  python3 find_pauses.py AUDIO.wav snap 3.64 6.40 10.8      # pausa mais proxima de cada instante (tempo do original)
  python3 find_pauses.py AUDIO.wav env 7.5 10.1             # envelope em passos de 10 ms (para cortar gaguejada)

Transicoes (flash, whoosh, clique) e cortes precisam cair em silencio, nunca em cima de uma palavra.
Os tempos de palavra do Whisper nao bastam: um corte feito so por eles comecou no meio de um "que".
"""
import sys
import numpy as np

path, mode, args = sys.argv[1], sys.argv[2], [float(a) for a in sys.argv[3:]]
import subprocess
sr = 16000
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(float) / 32768


def env(hop_s):
    hop = int(hop_s * sr)
    return np.array([20 * np.log10(np.sqrt((x[i:i + hop] ** 2).mean()) + 1e-9) for i in range(0, len(x) - hop, hop)])


if mode == "env":
    e = env(0.01)
    a, b = int(args[0] * 100), int(args[1] * 100)
    for k in range(a, b, 10):
        print(f"{k / 100:6.2f} " + " ".join(f"{int(v):4d}" for v in e[k:k + 10]))
else:
    e = env(0.02)
    for thr, minlen, win in [(-36, 0.12, 0.8), (-32, 0.08, 1.2)]:
        q = e < thr
        gaps, i = [], 0
        while i < len(q):
            if q[i]:
                j = i
                while j < len(q) and q[j]:
                    j += 1
                if (j - i) * 0.02 >= minlen:
                    gaps.append((i * 0.02, j * 0.02))
                i = j
            else:
                i += 1
        out = []
        for t in args:
            best = min(((abs((ga + gb) / 2 - t), ga, gb) for ga, gb in gaps), default=None)
            out.append((t, None if best is None or best[0] > win else (round((best[1] + best[2]) / 2, 2), round(best[1], 2), round(best[2], 2))))
        print(f"limiar {thr} dB:")
        for t, r in out:
            print(f"  {t:6.2f} -> {r}")
