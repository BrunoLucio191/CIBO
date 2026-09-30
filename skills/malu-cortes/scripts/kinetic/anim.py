# -*- coding: utf-8 -*-
"""Entrada, saida e micro-movimento das palavras como funcoes puras do tempo (adaptado do anim.py do Bombordo).

Na Malu tudo usa o Easy Ease cubic-bezier(0.33, 0, 0.67, 1): sem spring, sem ease_out_back, sem overshoot.
Cada preset devolve, para uma palavra no tempo local u (s desde o inicio da entrada):
dict(dx, dy, scale, alpha, blur, blur_dir, mask). blur_dir 'v'/'h' = blur direcional; 'g' = gaussiano.
Medidas em px no quadro 4K.
"""
from bezier import bezier, ease_in_out_sine

_E = {}


def E(cfg):
    k = tuple(cfg["motion"]["ease"])
    if k not in _E: _E[k] = bezier(*k)
    return _E[k]


def _p(u, d): return u / max(1e-3, d)


def slide_blur(u, cfg):
    """Ancora do estilo: sobe de leve com blur vertical que cai a zero."""
    D = cfg["timing"]["enter"]; m = cfg["motion"]; e = E(cfg)(_p(u, D))
    return dict(dx=0, dy=m["slide_px"] * (1 - e), scale=m["enter_scale_from"] + (1 - m["enter_scale_from"]) * e,
                alpha=E(cfg)(_p(u, D * 0.7)), blur=m["blur_px"] * (1 - e), blur_dir="v", mask=1.0)


def drop_blur(u, cfg):
    """Queda vertical: abre frase nova depois de pausa."""
    D = cfg["timing"]["enter"] * 1.1; m = cfg["motion"]; e = E(cfg)(_p(u, D))
    return dict(dx=0, dy=-m["slide_px"] * 1.1 * (1 - e), scale=m["enter_scale_from"] + (1 - m["enter_scale_from"]) * e,
                alpha=E(cfg)(_p(u, D * 0.6)), blur=m["blur_px"] * 1.1 * (1 - e), blur_dir="v", mask=1.0)


def mask_reveal(u, cfg):
    """Revelacao por mascara da esquerda para a direita, com blur horizontal."""
    D = cfg["timing"]["enter"] * 1.15; m = cfg["motion"]; e = E(cfg)(_p(u, D))
    return dict(dx=-m["slide_px"] * 0.5 * (1 - e), dy=0, scale=1.0, alpha=E(cfg)(_p(u, D * 0.45)),
                blur=m["blur_px"] * 0.6 * (1 - e), blur_dir="h", mask=e)


def soft_zoom(u, cfg):
    """Destaque: chega de 1,06 para 1 com blur que some. Substitui o pop_spring/zoom_blur do Bombordo."""
    D = cfg["timing"]["enter"] * 1.3; m = cfg["motion"]; e = E(cfg)(_p(u, D)); z0 = m["highlight_zoom_from"]
    return dict(dx=0, dy=0, scale=z0 - (z0 - 1) * e, alpha=E(cfg)(_p(u, D * 0.6)),
                blur=m["blur_px"] * 0.8 * (1 - e), blur_dir="g", mask=1.0)


def rise_blur(u, cfg):
    """Destaque alternativo: sobe como unidade com blur vertical."""
    D = cfg["timing"]["enter"] * 1.25; m = cfg["motion"]; e = E(cfg)(_p(u, D))
    return dict(dx=0, dy=m["slide_px"] * 1.1 * (1 - e), scale=0.97 + 0.03 * e, alpha=E(cfg)(_p(u, D * 0.6)),
                blur=m["blur_px"] * (1 - e), blur_dir="v", mask=1.0)


PRESETS = dict(slide_blur=slide_blur, drop_blur=drop_blur, mask_reveal=mask_reveal, soft_zoom=soft_zoom, rise_blur=rise_blur)
# o quanto cada entrada chega a subir acima da posicao final (para a folga do queixo)
RISE = dict(drop_blur=1.1, slide_blur=0.0, mask_reveal=0.0, soft_zoom=0.0, rise_blur=0.0)


def exit_tf(v, cfg, dur=None):
    """v = s desde o inicio da saida: some com ease, encolhe de leve e sobe ~15 px (30 no 4K)."""
    D = dur or cfg["timing"]["exit"]; m = cfg["motion"]; e = E(cfg)(_p(v, D))
    return dict(dy=-m["exit_push_px"] * e, scale=1 - (1 - m["exit_scale_to"]) * e, alpha=1 - e, blur=6 * e)


def idle_tf(t_in, life, cfg):
    """Micro-movimento: so a respiracao de escala (1 -> 1,012). Sem a oscilacao vertical do Bombordo."""
    return 1 + cfg["motion"]["idle_scale"] * ease_in_out_sine(t_in / max(0.8, life))
