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
    return round(sum(b - a for a, b in segments(job)), 3)


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
    pts, acc = [], 0.0
    segs = segments(job)
    for a, b in segs[:-1]:
        acc += b - a
        pts.append(round(acc, 3))
    return pts
