"""Shared helpers: config loading (defaults + per-video override), paths, text normalisation."""
import os, re, json, copy, unicodedata
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
DEFAULTS = os.path.join(HERE, 'config.yaml')


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(clip=None, project_cfg=None):
    cfg = yaml.safe_load(open(DEFAULTS, encoding='utf-8'))
    if project_cfg and os.path.exists(project_cfg):
        cfg = deep_merge(cfg, yaml.safe_load(open(project_cfg, encoding='utf-8')) or {})
    if clip:
        cfg = deep_merge(cfg, (cfg.get('videos') or {}).get(clip, {}))
    f = cfg['font']
    if not os.path.isabs(f):
        cfg['font'] = os.path.join(SKILL, 'assets', f)
    return cfg


def hex_rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def norm(w):
    w = unicodedata.normalize('NFD', w.lower())
    w = ''.join(c for c in w if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9%]', '', w)


def kdir(work):
    d = os.path.join(work, 'kinetic'); os.makedirs(d, exist_ok=True); return d


def jload(p): return json.load(open(p, encoding='utf-8'))


def jsave(obj, p): json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
