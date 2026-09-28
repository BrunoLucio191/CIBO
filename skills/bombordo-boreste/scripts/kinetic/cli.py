#!/usr/bin/env python3
"""Kinetic captions for Bombordo e Boreste cuts.

  JOB=job.json python3 cli.py align    [clip ...]   # Etapa 1: words_<clip>.json
  JOB=job.json python3 cli.py segment  [clip ...]   # Etapa 2: blocks_<clip>.json
  JOB=job.json python3 cli.py preview  <clip> [--start 0 --dur 8]
  JOB=job.json python3 cli.py render   <clip>
  JOB=job.json python3 cli.py render-all

Config: kinetic/config.yaml (defaults) + optional kinetic.yaml next to job.json
(same keys, plus `videos: {<clip>: {...}}` overrides). Output folder: job key
`kinetic_outdir` (never the original deliverables).
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from common import load_config, jload

JOBF = os.path.abspath(os.environ['JOB']); JOB = json.load(open(JOBF))
ROOT = os.path.dirname(JOBF)
WORK = os.path.join(ROOT, JOB.get('work', './work'))
PCFG = os.path.join(ROOT, 'kinetic.yaml')


def clips(args):
    out, skip = [], False
    for a in args:
        if skip: skip = False; continue
        if a.startswith('--'): skip = a in ('--start', '--dur'); continue
        out.append(a)
    return out or list(JOB['clips'])


def opt(args, name, default):
    return float(args[args.index(name) + 1]) if name in args else default


if __name__ == '__main__':
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'align':
        import align
        for k in clips(args): align.build(JOB, WORK, k)
    elif cmd == 'segment':
        import segment
        for k in clips(args): segment.build(JOB, WORK, k, load_config(k, PCFG))
    elif cmd in ('preview', 'render', 'render-all'):
        import pipeline
        ks = list(JOB['clips']) if cmd == 'render-all' else clips(args)
        for k in ks:
            cfg = load_config(k, PCFG)
            if cmd == 'preview':
                pipeline.preview(JOB, JOBF, WORK, k, cfg, opt(args, '--start', 0.0), opt(args, '--dur', 8.0))
            else:
                pipeline.render(JOB, JOBF, WORK, k, cfg)
    else:
        sys.exit(__doc__)
