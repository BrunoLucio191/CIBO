# Legendas animadas (kinetic typography)

Camada de legenda animada frame a frame (Pillow + NumPy + OpenCV, supersampling 2x),
encaixada no pipeline normal da skill (`make_reels.py`). Não usa ASS nem drawtext.

## Comandos (rodar na pasta do job)

```bash
PY=~/.codex/skills/podcast-reels/.venv/bin/python3
K=~/.claude/skills/bombordo-boreste/scripts/kinetic/cli.py
JOB=job.json $PY $K align   [corte..]   # 1. tempo por palavra  -> work/kinetic/words_<corte>.json
JOB=job.json $PY $K segment [corte..]   # 2. blocos + destaques -> work/kinetic/blocks_<corte>.json
JOB=job.json $PY $K preview <corte> --start 0 --dur 8   # prévia + folha de contatos
JOB=job.json $PY $K render  <corte>     # um corte final
JOB=job.json $PY $K render-all          # todos
```

Saída final: pasta `kinetic_outdir` do job.json (nunca sobrescreve os originais). Vídeo
H.264 CRF 18 yuv420p, mesma resolução/fps; o **áudio é copiado do vídeo original sem reencode**.

## Arquivos editáveis
- `words_<corte>.json` — `w`, `s`, `e` de cada palavra (segundos no vídeo, sem a capa).
  `correcoes` lista o que mudou em relação ao SRT; `divergencias_asr`, o que o modelo ouviu diferente.
- `blocks_<corte>.json` — blocos na tela; mova palavras, troque `hl` (destaque), `small`
  (palavra pequena acima do destaque) e `preset`. Depois de editar, rode `render` (não `segment`).
- `kinetic.yaml` (ao lado do job.json) — sobrescreve qualquer parâmetro abaixo, no geral ou
  por corte em `videos.<corte>`; `videos.<corte>.highlights` fixa os destaques por sentido.

## Parâmetros (`config.yaml`)
- `font`, `supersample` — fonte da sessão; renderiza em 2x e reduz (bordas limpas em movimento).
- `size.base` — tamanho base (px em 1080x1920). `highlight_scale` 1.8–2.2. `max_width` mantém
  o texto fora da coluna de botões. `line_pitch` entrelinha. `max_lines` 2. `highlight_lead_gap` — espaço entre a palavra pequena e o destaque grande logo abaixo.
- `color.base` / `active` — cor normal e da palavra sendo falada. `glow` / `glow_strength` —
  brilho do destaque. `shadow_*` — a mesma sombra da legenda estática.
- `position.band_height` — altura da faixa animada, centrada em `cap_cy` (abaixo do queixo,
  medido por corte). `safe_bottom`, `safe_x` — áreas seguras do Instagram.
- `timing.lead` — a palavra aparece ~1,5 frame antes do som. `enter` 180–250 ms, `exit`
  120–180 ms (encurta sozinho quando a fala é colada, para nunca sobrepor blocos),
  `color_fade`, `hold_after`, `min_block`.
- `motion.slide_px` 30–60, `blur_px` (blur direcional inicial, cai a 0), `enter_scale_from`,
  `exit_scale_to`, `exit_push_px`, `idle_scale`/`idle_drift_px` (vida na tela), `spring`.
- `presets.normal` — `slide_blur`, `drop_blur` (abre frase nova após pausa), `mask_reveal`.
  `presets.highlight` — `pop_spring`, `zoom_blur`, alternados (nunca o mesmo duas vezes seguidas).
- `segmentation` — `max_words`, `max_chars`, `pause_break` (pausa que fecha bloco),
  `highlight_every` (alvo: 1 destaque a cada 2–3 blocos), `min_blocks_between_highlights`.
- `punch_in.enabled` / `amount` / `duration` — zoom leve no vídeo em cada destaque (desligável).
