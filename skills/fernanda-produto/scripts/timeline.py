"""Linha do tempo da edicao: converte tempo do arquivo original para tempo do video editado."""
import json


def load_job(path):
    job = json.load(open(path))
    job["_path"] = path
    return job


def segments(job):
    """Trechos mantidos do original, em ordem: [(a, b), ...]."""
    segs, cur = [], job["in"]
    for a, b in sorted(job.get("cuts", [])):
        segs.append((cur, a))
        cur = b
    segs.append((cur, job["out"]))
    return [(round(a, 3), round(b, 3)) for a, b in segs if b - a > 0.05]


def duration(job):
    # tail_hold: segundos de imagem (audio mudo) depois da ultima fala, para o fade final nao engolir a palavra
    return round(sum(b - a for a, b in segments(job)) + job.get("tail_hold", 0), 3)


def o(job, t):
    """Tempo do original -> tempo editado. Um instante dentro de um corte cai no ponto do corte."""
    acc = 0.0
    for a, b in segments(job):
        if t < a:
            return round(acc, 3)
        if t <= b:
            return round(acc + (t - a), 3)
        acc += b - a
    return round(acc, 3)


def cut_points(job):
    """Instantes (tempo editado) em que ha emenda de corte, para o zoom seco que esconde o jump cut."""
    # punch_min: so cortes que removem pelo menos isso (s) ganham zoom seco; aparo de pausa curta fica corte seco
    pts, acc = [], 0.0
    segs = segments(job)
    for (a, b), (na, _) in zip(segs[:-1], segs[1:]):
        acc += b - a
        if na - b >= job.get("punch_min", 0):
            pts.append(round(acc, 3))
    return pts
