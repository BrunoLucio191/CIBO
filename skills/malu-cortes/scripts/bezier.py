# -*- coding: utf-8 -*-
"""Easy Ease do Premiere como curva CSS cubic-bezier, compartilhada por camera, legenda e graficos da Malu.

Copiada do punch.py do Bombordo (a skill de la nao e alterada): termina exatamente em 0 e 1 e recusa y fora de
[0, 1], que e overshoot. Na Malu spring e overshoot sao proibidos em qualquer animacao.
"""
import math

EASY_EASE = (0.33, 0.0, 0.67, 1.0)


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier(x1, y1, x2, y2) como p -> p suavizado. Monotonica, termina exatamente em 0/1."""
    if not (0 <= x1 <= 1 and 0 <= x2 <= 1):
        raise ValueError("cubic-bezier: x1/x2 precisam estar em [0, 1]")
    if not (0 <= y1 <= 1 and 0 <= y2 <= 1):
        raise ValueError("cubic-bezier: y fora de [0, 1] passa do ponto (overshoot) — proibido na Malu")
    cx = 3 * x1; bx = 3 * (x2 - x1) - cx; ax = 1 - cx - bx
    cy = 3 * y1; by = 3 * (y2 - y1) - cy; ay = 1 - cy - by
    X = lambda u: ((ax * u + bx) * u + cx) * u
    Y = lambda u: ((ay * u + by) * u + cy) * u

    def ease(p):
        if p <= 0: return 0.0
        if p >= 1: return 1.0
        lo, hi, u = 0.0, 1.0, p
        for _ in range(60):                      # bissecao: x(u) e monotonica em [0, 1]
            if X(u) < p: lo = u
            else: hi = u
            u = (lo + hi) / 2
            if hi - lo < 1e-9: break
        return Y(u)
    return ease


def ease_in_out_sine(p):
    p = 0.0 if p < 0 else 1.0 if p > 1 else p
    return -(math.cos(math.pi * p) - 1) / 2
