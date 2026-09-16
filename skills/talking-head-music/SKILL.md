---
name: talking-head-music
description: Select, compare, document, and mix background music for dialogue-led talking-head videos, podcast clips, Reels, Shorts, and business content. Use when music must support a speaker's emotion and cadence without reducing intelligibility; do not use for music videos or edits where the song is the primary content.
---

# Talking Head Music

**Local setup:** dependencies (numpy) live in a venv at
`~/.claude/skills/talking-head-music/.venv`. Run
`scripts/analyze_music.py` with
`~/.claude/skills/talking-head-music/.venv/bin/python3
scripts/analyze_music.py`, or activate that venv first, instead of the bare
`python3` shown below. Requires `ffmpeg`/`ffprobe` on PATH.

Choose music per cut, not per guest, episode, client folder, or genre label. The selected track must improve the spoken idea when heard under the voice; a good standalone song can still be the wrong underscore.

Read [references/scoring.md](references/scoring.md) before selecting or replacing tracks.

## Workflow

1. Read the cut or transcript through its final sentence. Record the subject, audience, purpose, emotional starting point, desired ending emotion, speaker energy, cadence, duration, and any turn or reveal.
2. Write one functional brief: instrumentation/texture, energy from 1–5, approximate BPM range, density, emotional arc, and what the music must not do.
3. Search the approved local library first. If it lacks a fit, use authorized sources and validate the item-level license. Do not infer rights from a platform name.
4. Analyze candidate files with `scripts/analyze_music.py`. Metrics help compare tempo, brightness, dynamics, crest factor, and source loudness; they do not replace listening under dialogue.
5. Shortlist three to five candidates. Reject vocals, dominant melodies, aggressive transients, excessive sub-bass, an emotional contradiction, or unclear commercial rights.
6. Audition the same 12–18 s speech section with each candidate at comparable perceived loudness. Also test the hook, the main turn, and the final sentence. Choose the candidate that makes those three moments clearer and more emotionally legible.
7. Select an intentional section of the track instead of always starting at 0:00. Record the source offset, music gain, ducking, fades, score, source page, license, author, and hash.
8. Measure the final mixed file and listen again after AAC encoding. Reconsider the track if the voice feels smaller, the rhythm fights sentence endings, or the conclusion loses impact.

## Mixing invariants

- Voice remains the anchor. Duck from the dialogue signal with a moderate attack and a release long enough to avoid pumping between words.
- Start conservatively; raise music only when it adds a perceptible emotional function.
- Align a build, downbeat, texture change, or harmonic resolution with an actual narrative turn. Never add impact merely because the track contains one.
- Preserve natural pauses. Do not use a gate or overactive automation to create artificial silence.
- If no candidate improves the cut, deliver without music or search again; do not keep a merely acceptable mismatch.

## Deliverables

Return a per-cut decision table with brief, candidates, weighted score, selected offset, mix level, license status, and rejection reasons. Store item-level attribution or license evidence when required.

## Entregar música e SFX em faixas separadas

O usuário quer poder ajustar o som depois sem novo render. Entregue dois arquivos:

1. **Arquivo editável:** vídeo + **A1 = voz + SFX** (default) + **A2 = música já com ducking** (`sidechaincompress` alimentado pela A1, fades e offset aplicados). Marque as faixas com `-metadata:s:a:0 title="Voz + SFX" -metadata:s:a:1 title="Musica" -disposition:a:0 default -disposition:a:1 0`.
2. **Cópia para postar:** o mesmo vídeo com `-c:v copy` e A1+A2 mixadas (`amix normalize=0` + `alimiter level=false`). Players e Instagram tocam só a primeira faixa, então o arquivo editável parece "sem música". Avise isso na entrega.

Mudanças só de volume (SFX mais baixo, música mais alta) se resolvem remixando o áudio com `-c:v copy`, em segundos, sem renderizar a imagem de novo. Guarde a trilha de SFX isolada (`sfx_track.wav`) para isso.

Para a música terminar junto com o vídeo, escolha o offset assim: `offset = fim_natural_da_faixa - duração_do_vídeo`. O vídeo começa com a faixa já com energia e acaba na resolução dela, sem fade cortado.
