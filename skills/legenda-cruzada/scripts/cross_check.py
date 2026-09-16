#!/usr/bin/env python3
"""Cross-check burned captions against an independent, stronger transcription.

One audio file per whisper call (the CLI overwrites its output when given
several inputs), context conditioning off (it loops on long audio), and a
memory fallback to the 8-bit model — never back to a turbo/distilled model,
which would just repeat the errors we are looking for.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys

FILLERS = {'e', 'é', 'a', 'o', 'as', 'os', 'um', 'uma', 'que', 'de', 'da', 'do',
           'na', 'no', 'em', 'né', 'aí', 'ah', 'então', 'se', 'eu', 'ele', 'ela'}


def sh(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def norm(text: str) -> list[str]:
    text = text.lower().replace('’', "'")
    text = re.sub(r'[^0-9a-záàâãéêíóôõúüç% ]', ' ', text)
    return [w for w in text.split() if w]


def burned_text(captions_dir: str, stem: str, clip_key: str) -> tuple[str, int]:
    """Caption source of truth: the engine's captions_<clip>.json, or an SRT."""
    for candidate in (os.path.join(captions_dir, f'captions_{clip_key}.json'),
                      os.path.join(captions_dir, f'{stem}.json')):
        if os.path.exists(candidate):
            caps = json.load(open(candidate, encoding='utf-8'))['caps']
            return ' '.join(c['t'] for c in caps), len(caps)
    srt = os.path.join(captions_dir, f'{stem}.srt')
    if os.path.exists(srt):
        blocks = re.split(r'\n\s*\n', open(srt, encoding='utf-8').read().strip())
        lines = []
        for b in blocks:
            rows = [x for x in b.strip().split('\n') if x.strip()]
            if len(rows) >= 3:
                lines.append(' '.join(rows[2:]))
        return ' '.join(lines), len(lines)
    raise SystemExit(f'sem legenda de referência para {stem} em {captions_dir}')


def transcribe(whisper: str, wav: str, out_dir: str, name: str,
               model: str, fallback: str, language: str) -> str:
    target = os.path.join(out_dir, f'{name}.json')
    if os.path.exists(target) and os.path.getsize(target) > 0:
        print(f'  {name}: já transcrito, pulando')
        return target
    for attempt, mdl in enumerate((model, fallback)):
        if not mdl:
            continue
        cmd = (f'"{whisper}" "{wav}" --model {mdl} --language {language} '
               f'--output-dir "{out_dir}" --output-name "{name}" '
               f'--output-format json --condition-on-previous-text False')
        sh(cmd)
        if os.path.exists(target) and os.path.getsize(target) > 0:
            print(f'  {name}: ok com {mdl}')
            return target
        print(f'  {name}: falhou com {mdl}'
              + (' (tentando modelo quantizado)' if attempt == 0 and fallback else ''))
    raise SystemExit(f'não consegui transcrever {name}: verifique memória livre e o modelo')


def classify(tag: str, burned: str, heard: str) -> str:
    words = set(burned.split()) | set(heard.split())
    if words and words <= FILLERS:
        return 'ruido'
    if tag == 'replace' and burned and heard:
        if difflib.SequenceMatcher(None, burned, heard).ratio() > 0.82:
            return 'revisar'          # near-identical: accent or spelling variant
        return 'suspeita'
    return 'revisar'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--videos', required=True, help='pasta com os MP4 entregues')
    ap.add_argument('--captions', required=True, help='pasta com captions_<clipe>.json ou .srt')
    ap.add_argument('--max-duration', type=float, default=300.0,
                    help='MP4 mais longo que isso nao e corte; fica fora da conferencia')
    ap.add_argument('--out', required=True, help='pasta de QA para áudio, JSONs e relatório')
    ap.add_argument('--model', default='mlx-community/whisper-large-v3-mlx')
    ap.add_argument('--fallback-model', default='mlx-community/whisper-large-v3-mlx-8bit')
    ap.add_argument('--whisper', default='mlx_whisper')
    ap.add_argument('--language', default='pt')
    ap.add_argument('--clip-prefix', default='corte',
                    help='prefixo das chaves captions_<prefixo><NN>.json')
    ap.add_argument('--min-ratio', type=float, default=0.85)
    args = ap.parse_args()

    audio_dir = os.path.join(args.out, 'legenda_cruzada_audio')
    text_dir = os.path.join(args.out, 'legenda_cruzada_transcricao')
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(text_dir, exist_ok=True)

    videos = sorted(f for f in os.listdir(args.videos) if f.lower().endswith('.mp4'))
    if not videos:
        raise SystemExit(f'nenhum MP4 em {args.videos}')

    # A pasta de entrega costuma guardar tambem o episodio inteiro ao lado dos
    # cortes. Sem esse filtro a conferencia comeca a transcrever uma hora de
    # video com o modelo grande e parece so estar lenta. O corte que exceder o
    # teto fica de fora com aviso, em vez de travar a verificacao toda.
    mantidos, pulados = [], []
    for v in videos:
        dur = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                              'format=duration', '-of', 'csv=p=0',
                              os.path.join(args.videos, v)],
                             capture_output=True, text=True).stdout.strip()
        try:
            dur = float(dur)
        except ValueError:
            dur = 0.0
        (mantidos if dur <= args.max_duration else pulados).append((v, dur))
    if pulados:
        print('fora da conferencia por duracao (use --max-duration para mudar):')
        for v, d in pulados:
            print(f'  {v}  {d/60:.0f} min')
    videos = [v for v, _ in mantidos]
    if not videos:
        raise SystemExit('todos os MP4 passaram do teto de duracao; nada a conferir')

    report, blocked = {}, []
    for index, video in enumerate(videos, start=1):
        stem = video[:-4]
        clip_key = f'{args.clip_prefix}{index:02d}'
        name = clip_key
        print(f'[{index}/{len(videos)}] {stem}')
        wav = os.path.join(audio_dir, f'{name}.wav')
        if not os.path.exists(wav):
            sh(f'ffmpeg -nostdin -v error -i "{os.path.join(args.videos, video)}" '
               f'-vn -ac 1 -ar 16000 "{wav}" -y')
        heard_json = transcribe(args.whisper, wav, text_dir, name,
                                args.model, args.fallback_model, args.language)

        burned_raw, blocks = burned_text(args.captions, stem, clip_key)
        burned = norm(burned_raw)
        heard = norm(' '.join(s['text'] for s in
                              json.load(open(heard_json, encoding='utf-8'))['segments']))
        matcher = difflib.SequenceMatcher(None, burned, heard)
        items = []
        for tag, a1, a2, b1, b2 in matcher.get_opcodes():
            if tag == 'equal':
                continue
            leg, aud = ' '.join(burned[a1:a2]), ' '.join(heard[b1:b2])
            items.append(dict(tipo=tag, legenda=leg, audio=aud,
                              classe=classify(tag, leg, aud)))
        ratio = round(matcher.ratio(), 4)
        suspects = [i for i in items if i['classe'] == 'suspeita']
        report[stem] = dict(clip=clip_key, similaridade=ratio, blocos=blocks,
                            divergencias=len(items), suspeitas=len(suspects),
                            itens=items)
        flag = ''
        if ratio < args.min_ratio:
            flag = '  << ABAIXO DO MINIMO'
            blocked.append(stem)
        print(f'  similaridade={ratio:.3f} blocos={blocks} '
              f'divergências={len(items)} suspeitas={len(suspects)}{flag}')
        for s in suspects:
            print(f'      suspeita: legenda[{s["legenda"][:48]}] audio[{s["audio"][:48]}]')

    json.dump(report, open(os.path.join(args.out, 'legenda_cruzada.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, 'legenda_cruzada.md'), 'w', encoding='utf-8') as fh:
        fh.write('# Verificação cruzada de legenda\n\n')
        fh.write(f'Modelo de conferência: `{args.model}` '
                 f'(fallback `{args.fallback_model}`)\n\n')
        fh.write('| Arquivo | Similaridade | Blocos | Divergências | Suspeitas |\n')
        fh.write('|---|---|---|---|---|\n')
        for stem, r in report.items():
            fh.write(f'| {stem} | {r["similaridade"]:.3f} | {r["blocos"]} | '
                     f'{r["divergencias"]} | {r["suspeitas"]} |\n')
        total = sum(r['suspeitas'] for r in report.values())
        fh.write(f'\n{len(report)} arquivos, {total} divergências suspeitas.\n')
        if blocked:
            fh.write('\n**Bloqueados por similaridade baixa:** '
                     + ', '.join(blocked) + '\n')

    print(f'\nrelatório: {os.path.join(args.out, "legenda_cruzada.md")}')
    if blocked:
        print('BLOQUEADO:', ', '.join(blocked))
        sys.exit(2)


if __name__ == '__main__':
    main()
