# -*- coding: utf-8 -*-
"""Named easing curves + slide/fade entrance offsets, shared by every caption/lettering renderer.

Curve names follow the convention used across most animation libraries
(Penner-style: ease_in/out/in_out + Quad/Cubic/Back/Bounce), so a preset name
in job.json means the same thing here as it would anywhere else.
"""

def linear(p): return p
def ease_in_quad(p): return p*p
def ease_out_quad(p): return 1-(1-p)**2
def ease_in_out_quad(p): return 2*p*p if p < 0.5 else 1-(-2*p+2)**2/2
def ease_in_cubic(p): return p**3
def ease_out_cubic(p): return 1-(1-p)**3
def ease_in_out_cubic(p): return 4*p**3 if p < 0.5 else 1-(-2*p+2)**3/2
def ease_out_back(p, c1=1.15):
    c3 = c1+1.0
    return 1.0+c3*(p-1.0)**3+c1*(p-1.0)**2
def ease_out_bounce(p):
    n1, d1 = 7.5625, 2.75
    if p < 1/d1: return n1*p*p
    if p < 2/d1: p -= 1.5/d1; return n1*p*p+0.75
    if p < 2.5/d1: p -= 2.25/d1; return n1*p*p+0.9375
    p -= 2.625/d1
    return n1*p*p+0.984375

CURVES = {
    'linear': linear,
    'ease_in_quad': ease_in_quad, 'ease_out_quad': ease_out_quad, 'ease_in_out_quad': ease_in_out_quad,
    'ease_in_cubic': ease_in_cubic, 'ease_out_cubic': ease_out_cubic, 'ease_in_out_cubic': ease_in_out_cubic,
    'ease_out_back': ease_out_back, 'ease_out_bounce': ease_out_bounce,
}

DIRECTIONS = {  # unit (dx, dy) an element travels FROM, arriving at offset (0, 0)
    'up': (0, 1), 'down': (0, -1), 'left': (1, 0), 'right': (-1, 0),
}

def clamp01(p): return 0.0 if p < 0 else 1.0 if p > 1 else p

def slide_offset(progress, direction='up', distance=40, ease=ease_out_cubic):
    """Pixel (dx, dy) to ADD to an element's resting position at this progress (0..1)."""
    ux, uy = DIRECTIONS[direction]
    remaining = 1.0-ease(clamp01(progress))
    return ux*distance*remaining, uy*distance*remaining

def fade(progress, ease=ease_out_cubic):
    return clamp01(ease(clamp01(progress)))

def entrance(progress, direction='up', distance=40, pos_ease=ease_out_cubic, fade_ease=None):
    """Slide-in + fade-in combo: starts at 0 opacity, offset `distance` px in `direction`
    from its resting position, and eases into full opacity at (0, 0) by progress=1.
    fade_ease defaults to pos_ease so opacity and position finish together."""
    dx, dy = slide_offset(progress, direction, distance, pos_ease)
    alpha = fade(progress, fade_ease or pos_ease)
    return dx, dy, alpha
