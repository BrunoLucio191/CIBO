#!/usr/bin/env python3
"""Escolhe o melhor frame de um trecho para virar capa.

Detecta rosto com YuNet e pontua tamanho, nitidez, exposicao, olhos abertos
(variancia na regiao dos olhos), simetria e enquadramento no crop 9:16.
Uso: pick_frame.py <video> <ini> <fim> <saida.png>
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

import os as _os
_AQUI = _os.path.dirname(_os.path.abspath(__file__))
ASSETS = _os.path.join(_os.path.dirname(_AQUI), "assets")
# RAIZ e a pasta do projeto do episodio; os assets vem da skill.
RAIZ = _os.environ.get("PROJETO", _os.getcwd())


MODELO = _os.path.join(ASSETS, "yunet.onnx")
N_AMOSTRAS = 90


def detector(w, h):
    return cv2.FaceDetectorYN.create(MODELO, "", (w, h), 0.75, 0.3, 5000)


def nitidez(img):
    if img.size == 0:
        return 0.0
    return cv2.Laplacian(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def pontua(im, det):
    h, w = im.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(im)
    if faces is None or len(faces) == 0:
        return -1, None

    # maior rosto do frame
    f = max(faces, key=lambda r: r[2] * r[3])
    x, y, fw, fh = [int(v) for v in f[:4]]
    conf = float(f[-1])
    olho_d = (f[4], f[5])
    olho_e = (f[6], f[7])

    x, y = max(x, 0), max(y, 0)
    face = im[y:y + fh, x:x + fw]
    if face.size == 0:
        return -1, None

    # rosto grande = plano fechado, melhor pra capa.
    # plano aberto (rosto minusculo) nao serve como capa: descarta de vez
    if fw < w * 0.085:
        return -1, None
    s_tam = min(fw / (w * 0.22), 1.0)
    s_nit = min(nitidez(face) / 300.0, 1.0)

    # exposicao: penaliza rosto escuro demais ou estourado
    med = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY).mean()
    s_exp = 1.0 - min(abs(med - 125) / 105.0, 1.0)

    # olhos abertos: regiao do olho fechada fica lisa, aberta tem contraste
    def detalhe_olho(pt):
        r = max(int(fw * 0.10), 6)
        cx, cy = int(pt[0]), int(pt[1])
        reg = im[max(cy - r, 0):cy + r, max(cx - r, 0):cx + r]
        if reg.size == 0:
            return 0.0
        g = cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY)
        return float(g.std())

    ed = (detalhe_olho(olho_d) + detalhe_olho(olho_e)) / 2
    s_olho = min(ed / 42.0, 1.0)

    # cabeca reta: linha dos olhos aproximadamente horizontal
    dy = abs(olho_d[1] - olho_e[1]); dx = abs(olho_d[0] - olho_e[0]) + 1e-6
    s_reta = 1.0 - min((dy / dx) / 0.34, 1.0)

    # rosto precisa cair na faixa central preservada pelo crop 9:16
    cxf = (x + fw / 2) / w
    s_pos = 1.0 - min(abs(cxf - 0.5) / 0.40, 1.0)

    total = (s_tam * 0.34 + s_nit * 0.18 + s_olho * 0.20
             + s_pos * 0.12 + s_reta * 0.08 + s_exp * 0.08)
    return total, dict(t_x=cxf, conf=conf, tam=s_tam, nit=s_nit,
                       olho=s_olho, pos=s_pos, exp=s_exp)


def main():
    video, ini, fim, saida = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
    tmpd = tempfile.mkdtemp(dir=os.path.dirname(saida) or ".")
    # evita as pontas, onde costuma haver troca de camera
    tempos = np.linspace(ini + 0.8, fim - 0.8, N_AMOSTRAS)
    det = None

    melhor = (-1, None, None, None)
    for i, t in enumerate(tempos):
        f = f"{tmpd}/f{i:03d}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}",
                        "-i", video, "-frames:v", "1", f], check=True)
        im = cv2.imread(f)
        if im is None:
            continue
        if det is None:
            det = detector(im.shape[1], im.shape[0])
        pt, info = pontua(im, det)
        if pt > melhor[0]:
            melhor = (pt, f, t, info)

    pt, f, t, info = melhor
    if f is None:
        print("NENHUM ROSTO ENCONTRADO", file=sys.stderr)
        sys.exit(2)
    subprocess.run(["cp", f, saida], check=True)
    subprocess.run(["rm", "-rf", tmpd])
    det_str = " ".join(f"{k}={v:.2f}" for k, v in info.items())
    print(f"{saida}\tt={t:.2f}\tscore={pt:.3f}\t{det_str}")


if __name__ == "__main__":
    main()
