"""Rastreamento de rosto por plano: matriz no rosto, parada x movimento, enquadramento travado ou seguindo.

Uso (venv ~/.venvs/audiotools, que tem opencv):
  face_track.py job.json [--levels 1500 1300 1050] [--apply] [--debug qa/face_track.mp4]

Para cada plano de job["shots"] (tempo do original, nivel = 0 aberto, 1 medio, 2 fechado):
- detecta o rosto (OpenCV YuNet: caixa + olhos, nariz, cantos da boca) a 10 fps;
- mede o movimento do centro do rosto em alturas-de-rosto por segundo -> PARADA / MOVENDO;
- enquadra como um operador: olhos a ~1/3 da altura e espaco de olhar do lado para onde ela olha;
- se o rosto sairia da zona segura do quadro travado (> 12% da largura ou olhos fora de 22-45% da altura),
  o plano MERECE SER SEGUIDO: gera um caminho de camera com zona morta + amortecimento (nao treme a cada gesto);
  senao, o plano fica TRAVADO (a escolha padrao de um editor: so seguir quando precisa).
--apply grava em job["framings"] um enquadramento por plano (estatico [x,y,w,h] ou {"w","h","kx","ky"}) e
aponta cada plano para o seu. --debug gera o video de diagnostico com a matriz desenhada.
"""
import argparse, json, os, subprocess, sys
from pathlib import Path
import numpy as np, cv2

ap = argparse.ArgumentParser()
ap.add_argument("job"); ap.add_argument("--levels", nargs=3, type=int, default=[1500, 1300, 1050])
ap.add_argument("--apply", action="store_true"); ap.add_argument("--debug")
ap.add_argument("--fps", type=float, default=10.0)
a = ap.parse_args()
job = json.load(open(a.job))
SRC = job["src"]; FW, FH = 2160, 3840          # quadro em pe depois do transpose
DW, DH = 540, 960; S = FW / DW                   # analise em 1/4
MODEL = str(Path.home() / ".cache/yunet/face_detection_yunet_2023mar.onnx")
det = cv2.FaceDetectorYN.create(MODEL, "", (DW, DH), 0.6, 0.3, 5000)


def frames(t0, t1):
    rot = "transpose=clock," if job.get("rotate", "clock") == "clock" else ""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-noautorotate", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", SRC,
                          "-vf", f"{rot}scale={DW}:{DH},fps={a.fps}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True).stdout
    n = len(raw) // (DW * DH * 3)
    return np.frombuffer(raw[:n * DW * DH * 3], np.uint8).reshape(n, DH, DW, 3)


def detect(img):
    _, f = det.detect(img)
    if f is None or not len(f): return None
    f = max(f, key=lambda r: r[2] * r[3])        # maior rosto = a falante
    x, y, w, h = f[:4]; lm = f[4:14].reshape(5, 2)  # olho dir, olho esq, nariz, boca dir, boca esq
    return dict(box=(x, y, w, h), lm=lm, c=(x + w / 2, y + h / 2), eye=lm[:2].mean(0), score=float(f[14]))


def fill(track):
    """Interpola quadros sem deteccao (rosto de perfil, mao na frente)."""
    idx = [i for i, d in enumerate(track) if d]
    if not idx: return None
    for i in range(len(track)):
        if track[i] is None:
            j = min(idx, key=lambda k: abs(k - i)); track[i] = track[j]
    return track


def camera(target, dz, tau, dt, vmax):
    """Operador de camera: parado enquanto o alvo esta dentro da zona morta; fora dela persegue com amortecimento
    (constante tau) e velocidade maxima vmax (px/s). Evita 'camera nervosa' seguindo cada gesto."""
    c = [target[0]]; v = 0.0
    for t in target[1:]:
        err = t - c[-1]
        goal = 0.0 if abs(err) <= dz else (err - np.sign(err) * dz) / tau
        v += (goal - v) * min(1.0, dt / (tau * 0.5))
        v = float(np.clip(v, -vmax, vmax))
        c.append(c[-1] + v * dt)
    return np.array(c)


shots = job["shots"]; dt = 1 / a.fps
# depois de um --apply o 3o campo do plano vira indice de framing; o nivel fica em shot_levels
LV = job.get("shot_levels") or [s[2] for s in shots]
shots = [[t0, t1, LV[i]] for i, (t0, t1, _) in enumerate(shots)]
report, new_framings, dbg, face_pos = [], [], [], []
for si, (t0, t1, lv) in enumerate(shots):
    F = frames(t0, t1)
    tr = fill([detect(f) for f in F])
    Wc = a.levels[lv if lv is not None else 0]; Hc = int(round(Wc * 16 / 9 / 2) * 2)
    if tr is None:
        report.append(dict(plano=si, estado="sem rosto", decisao="travado padrao")); new_framings.append(job["framings"][lv])
        face_pos.append([0.5, 0.33]); continue
    cx = np.array([d["c"][0] for d in tr]) * S; ey = np.array([d["eye"][1] for d in tr]) * S
    fh = np.median([d["box"][3] for d in tr]) * S
    nose_off = np.median([(d["lm"][2][0] - d["eye"][0]) / max(d["box"][2], 1) for d in tr])
    # espaco de olhar: nariz a esquerda do meio dos olhos = olha para a esquerda -> rosto um pouco a direita
    look = "esquerda" if nose_off < -0.04 else ("direita" if nose_off > 0.04 else "frente")
    fx = {"esquerda": 0.56, "direita": 0.44, "frente": 0.50}[look]
    ex = 0.36 if lv == 2 else 0.33               # olhos a ~1/3 (um pouco mais baixo no fechado)
    tx = cx - fx * Wc; ty = ey - ex * Hc          # canto do recorte que poe o rosto no lugar certo
    sp = np.hypot(np.diff(cx), np.diff(ey)) / dt / fh if len(cx) > 1 else np.array([0.0])
    speed = float(np.median(sp)) if len(sp) else 0.0
    moving = float(np.percentile(sp, 80)) if len(sp) else 0.0
    lock_x, lock_y = float(np.median(tx)), float(np.median(ty))
    dev_x = float(np.max(np.abs(tx - lock_x)) / Wc); ey_rel = (ey - lock_y) / Hc
    follow = dev_x > 0.12 or ey_rel.min() < 0.22 or ey_rel.max() > 0.45
    clampx = lambda v: np.clip(v, 0, FW - Wc); clampy = lambda v: np.clip(v, 0, FH - Hc)
    if follow:
        px = clampx(camera(tx, 0.06 * Wc, 0.6, dt, 0.35 * Wc)); py = clampy(camera(ty, 0.05 * Hc, 0.8, dt, 0.25 * Hc))
        keys = lambda p: [[round(k * dt, 2), int(round(v))] for k, v in list(enumerate(p))[::3]] + [[round((len(p) - 1) * dt, 2), int(round(p[-1]))]]
        fr = {"w": Wc, "h": Hc, "kx": keys(px), "ky": keys(py)}
    else:
        px = np.full(len(tx), clampx(lock_x)); py = np.full(len(ty), clampy(lock_y))
        fr = [int(round(px[0])), int(round(py[0])), Wc, Hc]
    new_framings.append(fr)
    face_pos.append([fx, ex])                     # onde o rosto fica no quadro deste plano (fracao) -> ancora do zoom
    estado = "PARADA" if moving < 0.35 else "MOVENDO"
    report.append(dict(plano=si, t=f"{t0:.2f}-{t1:.2f}", nivel=lv, estado=estado, vel_mediana=round(speed, 2),
                       vel_p80=round(moving, 2), desvio_lateral=round(dev_x, 3), olhar=look,
                       decisao="SEGUIR" if follow else "travado"))
    if a.debug:
        trail = []
        for k, (img, d) in enumerate(zip(F, tr)):
            im = img.copy(); x, y, w, h = [int(v) for v in d["box"]]
            # matriz no rosto: caixa + grade 3x3 + pontos do rosto
            cv2.rectangle(im, (x, y), (x + w, y + h), (0, 255, 255), 1)
            for g in (1, 2):
                cv2.line(im, (x + g * w // 3, y), (x + g * w // 3, y + h), (0, 200, 255), 1)
                cv2.line(im, (x, y + g * h // 3), (x + w, y + g * h // 3), (0, 200, 255), 1)
            for p in d["lm"]: cv2.circle(im, (int(p[0]), int(p[1])), 3, (255, 0, 255), -1)
            trail.append((int(d["c"][0]), int(d["c"][1])))
            for p, q in zip(trail[-15:], trail[-14:]): cv2.line(im, p, q, (0, 0, 255), 2)
            # recorte que o video final vai usar neste quadro
            rx, ry = int(px[k] / S), int(py[k] / S); rw, rh = int(Wc / S), int(Hc / S)
            col = (0, 140, 255) if follow else (0, 220, 0)
            cv2.rectangle(im, (rx, ry), (rx + rw, ry + rh), col, 2)
            cv2.line(im, (rx, ry + rh // 3), (rx + rw, ry + rh // 3), col, 1)
            v = sp[min(k, len(sp) - 1)] if len(sp) else 0
            cv2.rectangle(im, (0, 0), (DW, 58), (0, 0, 0), -1)
            cv2.putText(im, f"plano {si} N{lv}  {'SEGUIR' if follow else 'TRAVADO'}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            cv2.putText(im, f"{'MOVENDO' if v >= 0.35 else 'PARADA'}  {v:.2f} rostos/s  olhar {look}", (8, 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            dbg.append(im)

for r in report:
    print(" ".join(f"{k}={v}" for k, v in r.items()))
if a.apply:
    job["framings"] = new_framings
    job["shots"] = [[t0, t1, i] for i, (t0, t1, _) in enumerate(shots)]
    job["shot_levels"] = [lv for _, _, lv in shots]   # nivel de enquadramento de cada plano (para revisao)
    job["face_pos"] = face_pos                          # [x do rosto, y dos olhos] por plano: ancora do zoom centrado
    json.dump(job, open(a.job, "w"), ensure_ascii=False, indent=1)
    print("framings por plano gravados no job")
if a.debug and dbg:
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{DW}x{DH}", "-r", str(a.fps),
                          "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", a.debug], stdin=subprocess.PIPE)
    for im in dbg: p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait(); print("diagnostico:", a.debug)
