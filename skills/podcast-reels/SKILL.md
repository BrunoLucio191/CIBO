---
name: podcast-reels
description: Turn a long podcast episode plus its SRT into vertical 9:16 Reels/TikTok/Shorts cuts with baseline-aligned Cal Sans captions, emphasis lettering, camera-click SFX, a blue film-burn intro, an eased zoom-out-with-blur opener, and a headline cover. Use when the user asks for "cortes", clips, Reels, Shorts or TikToks from a podcast, or wants captions burned into a vertical clip.
---

# Podcast → Reels

**Local setup:** dependencies (Pillow, numpy) live in a venv at
`~/.claude/skills/podcast-reels/.venv`. Run scripts with
`~/.claude/skills/podcast-reels/.venv/bin/python3 scripts/make_reels.py`, or
`source ~/.claude/skills/podcast-reels/.venv/bin/activate` first, instead of the
bare `python3` shown below. Requires `ffmpeg`/`ffprobe` on PATH (already present
via Homebrew).


Builds finished vertical cuts from a master video + SRT. Everything is driven by one
`job.json`; the scripts do transcription-free caption timing (reused from the SRT),
silence-snapped trimming, caption rendering, audio sweetening and the cover.

## Workflow

1. **Read the SRT, not the video.** Collapse it into a readable transcript first:
   group cues into ~15 s blocks and print `[start - end] text`. Pick the clips from
   that. Never scrub the video looking for moments.
2. **Identify host vs guest** from conversational flow (who introduces, who asks,
   who answers) and say so before proposing cuts.
3. **Pick moments** with a hook in the first 3 s, one clear idea, and a closing
   punchline or a cliffhanger question. Target 42–55 s of *kept* audio — the trim
   removes 15–25 % of the raw window, so choose a window ~20 % longer.
4. **Write `job.json`** (see `assets/job.example.json`) with, per clip: `src`,
   `master_in` (its IN point in the master, seconds — used to map SRT cues),
   `headline`, `filename` (the delivered basename — never leave this as the clip
   key; deliverables must be named after the headline, e.g.
   `01 - ELEGANCIA NAO E - FICAR INVISIVEL - DEPOIS DOS 50`, matching the cover's
   `CAPA - <filename>.png`), `cropx`, `cover_t`, and `keeps` (list of `[start,end]`
   in *clip-local* seconds).
5. **Run it:**
   ```bash
   JOB=job.json python3 scripts/make_reels.py            # all clips
   JOB=job.json python3 scripts/make_reels.py corte01    # one clip
   ```

## Choosing `keeps`

`keeps` is the edit. Drop filler, false starts, repeated phrases and dead air; keep
whole clauses. Boundaries are then **snapped automatically** to the quietest 10 ms
frame within ±160 ms and given 35 ms/55 ms fades, so cuts land in breaths instead of
on top of a word. Do not hand-tune to the millisecond — snap it.

The first `keeps` start and the last end are never snapped, so the clip opens and
closes exactly where you asked.

## What the pipeline produces

| Stage | What it does |
|---|---|
| `plan.py` | snaps keeps to silence, maps SRT cues through the trim, merges them into ≤18-char captions, flags emphasis words |
| `render_caps.py` | draws captions to a 1080×420 band as two H.264 streams (colour + alpha matte) — fast and small |
| `clicks.py` | synthesises a soft shutter click, one per emphasis caption |
| `render.py` | cut+crop+scale with a per-segment eased ken-burns zoom, eased zoom-out with blur opener (Python, frame-exact), screen-blends the blue film burn, overlays captions, mixes clicks, prepends the cover — **all in one x264 pass** |
| `cover.py` | grabs `cover_t`, adds scrim + headline + logo → `capa_*.png` |

## Changing a finished cut

This is the common case, and it must not cost a full rebuild. Stages are
fingerprinted in `work/.stamps.json`; only what actually changed re-renders.
A no-op run is ~0.5 s.

| Request | Edit | Rebuilds | Cost |
|---|---|---|---|
| wrong word, bad line break, emphasis | `work/captions_<clip>.json` | caps → compose → deliver | ~35 s |
| caption position / size / colour | `job.style`, then `REPLAN=0` | caps → compose → deliver | ~35 s |
| headline or cover frame | `job.clips.<k>.headline` / `cover_t` | cover → deliver | ~8 s |
| trim, extend, drop a beat | `job.clips.<k>.keeps` + `REPLAN=1` | everything | ~2 min |
| framing | `cropx` | everything | ~2 min |
| bitrate / size | `crf`, `preset`, `extra_v` | deliver | ~15 s |

`work/captions_<clip>.json` is the source of truth once it exists — `plan.py` will
not overwrite it unless `REPLAN=1`. Hand-edit `t`, `w` and `em` there; that is where
a Portuguese fix belongs after the first pass. `work/review.csv` maps every caption to
its timecode **in the delivered file** (cover included), so a note like "aos 12 s está
errado" resolves to a row without opening the video.

## Never render a full clip to look at something

```bash
JOB=job.json python3 scripts/tools.py probe corte01 12 18   # 6 s @540p, ~2 s
JOB=job.json python3 scripts/tools.py sheet corte01         # 8-frame sheet, ~2 s
```

`sheet` crops to the caption band. Run it after **any** visual change and actually
look at it before rendering or delivering. Every visual bug in this skill's history
was visible in a contact sheet and got caught only after a full render instead.

## Known failure modes — check these first

These all shipped once. Do not rediscover them.

1. **Captions look crooked.** Words were centred by their own bounding box, so `o`,
   `aí`, `É` float. Position by font ascent on a shared baseline. Already fixed —
   don't "simplify" `build_caption` back.
2. **Whole frame goes magenta.** `blend=all_mode=screen` ran on YUV and screened the
   chroma planes. Both inputs need `format=gbrp` first.
3. **Caption band renders as an opaque black bar.** `libvpx-vp9` in some builds
   accepts `-pix_fmt yuva420p` and silently writes `yuv420p`. Verify with `ffprobe`,
   or use the colour + `alphaextract` matte pair this skill ships.
4. **Cuts sound abrupt.** Boundaries land mid-word. Snapping to the quietest frame
   within ±160 ms plus 35/55 ms fades fixes it; the first start and last end are
   deliberately never snapped.
5. **File too big to deliver.** ~30 MB to the conversation, ~20 MB to a connected
   folder. Decide the target *before* rendering: `crf 24` + `maxrate 2900k` puts a
   47 s 1080×1920 clip at ~18 MB. Full quality means rendering on the user's machine.
6. **A clip comes out too short.** Trimming removes 15–25 %. Pick the source window
   ~20 % longer than the target, then check `total` in `plan.json` before rendering.
7. **Encoding the same frames twice.** Composing to an intermediate and then
   re-encoding it to glue the 1 s cover on the front doubled the cost of every
   change (130 s instead of 54 s per clip). `render.final()` takes `cover=` and
   emits the deliverable in a single pass — never chain a second full encode.
8. **A static talking head reads as dead.** `ZOOM_AMT` (default 0.055) gives each
   kept segment its own slow push-in / pull-out, alternating direction per cut,
   eased in and out. The source is oversampled by the same amount before
   `zoompan` so the move costs no sharpness. Set `ZOOM_AMT=0` to disable.
9. **Synthesised SFX sound cheap.** Point `CLICK` at a real sample (`assets/click.wav`);
   it is trimmed to its transient and normalised to `CLICK_GAIN` (default 0.22).
10. **Background jobs die.** On the desktop bridge each shell call is its own process
   group — `nohup`/`setsid` do not survive. Every ffmpeg call must finish inside one
   call (~45 s), so chunk long renders.
11. **Ken-burns zoom looks shaky/vibrating.** `passA`'s pre-`zoompan` oversample (`OS`/
    `OSW`) was computed from the *native crop* size (608×1080) instead of the *final
    output* size (1080×1920) — zoompan was fed a ~654×1161 source and had to do most of
    the 1080×1920 upscale itself with its own weaker scaler, which shimmers as the crop
    shifts fractionally frame to frame. Fixed: base the oversample on `W,H` so zoompan
    only ever crops and lightly downscales from an already-adequate source.
12. **A variable-weight font (e.g. Montserrat) renders too thin for captions/cover.**
    `ImageFont.truetype` on a variable font loads its default named instance, which
    for most families is Regular, not Bold. `render_caps.py` and `cover.py` call
    `set_variation_by_name(os.environ.get('FONT_WEIGHT','Bold'))` after loading —
    check the font's actual instance names first (fontTools `fvar` table) if
    `'Bold'` doesn't exist for a given font.
13. **A click SFX steps on the opening word.** `clicks.py` fires on every caption flagged
    `any` (emphasis), including caption 0 — if the clip's first word is in `job.emph`
    (common: it's usually the hook stat), the click lands right on top of it and sounds
    like the voice glitching. Fixed: skip `idx==0` in `clicks.build`. Emphasis styling
    (bigger text) on the opening word is still fine — only the audio click is suppressed.
14. **A long, unfragmented SRT cue ships as one on-screen wall of text.**
    `plan.py`'s caption builder only *merges* short adjacent SRT cues up to the
    18-char limit — it never *split* a cue that was already longer than that on
    its own. Whisper (or whatever produced the SRT) doesn't reliably break every
    sentence into short cues; a fluent passage with few pauses can land as one
    40-60 character segment, rendered motionless on screen for its whole
    duration instead of the intended short auto-wrapped captions. Fixed: atoms
    longer than 18 chars are now split into word-packed chunks before merging,
    with time apportioned by character count across the original cue's span.
    Caught by `caption-quality-gate`'s `block_long` warning — run it on every
    delivered clip, not just a visual spot-check.
15. **`music`/`mix`/`filename` silently vanish from the render.** `plan.py`'s
    `build()` used to return a hand-picked dict of fields (`name`, `src`, `keeps`,
    `total`, `headline`, `cropx`, `cover_t`, `caps`) as `plan.json`, which
    `make_reels.py` then reads as the clip config for every later stage —
    anything in `job.clips.<k>` that wasn't in that hand-picked list (`music`,
    `mix`, `filename`, a per-clip `logo`, ...) got dropped with no error, no
    warning, nothing in the render log. Result: 8 clips rendered "successfully"
    with zero background music despite a correct `job.json`. Fixed: `build()`
    now merges every other key from the original clip dict into its result
    before returning. If a job field doesn't show up in the render, check
    `work/plan.json` first — if it's missing there, no downstream code will
    ever see it, no matter how correct the JSON you wrote is.



16. **A imagem desliza de lado numa emenda.** O reenquadramento por deteccao de
    rosto (`face_crop.py`, na skill `bombordo-boreste`) fechava um recorte por
    **trecho mantido** em vez de por **plano de camera**: dois keeps do mesmo
    plano recebiam medianas de rosto diferentes — o falante se mexeu — e o
    `cropx` pulava de 0.485 para 0.520, ou seja ~46 px numa janela de 608 sobre
    1920, exatamente em cima de uma emenda onde a camera nunca cortou. Na tela
    isso le como erro de montagem. Corrigido: as deteccoes sao agrupadas por
    plano de camera (a comparacao de cena continua valendo tambem na junção
    entre dois keeps, entao um corte de camera dentro do trecho descartado ainda
    e detectado) e cada plano recebe um unico recorte. **Regra: `cropx` so pode
    mudar onde a camera corta de verdade.** A unica excecao aceitavel e trocar de
    falante dentro de um plano aberto, e mesmo assim so quando a troca cai
    exatamente sobre uma emenda que ja muda quem fala.
17. **Uma legenda mostra frase que foi cortada fora.** O mapeamento de cue para
    trecho mantido usava `if e2-s2>0.12`: bastavam 0,13 s de um cue caírem dentro
    do keep para o texto **inteiro** dele ir para a tela, mesmo com o audio
    daquela frase inteiramente descartado. Corrigido: acima de 85% de
    sobreposicao o cue vai inteiro; abaixo disso so vao as palavras
    proporcionais ao trecho ouvido; e se nao sobra nada legivel, o atomo e
    descartado. Note que o snap de silencio move a fronteira em ate ±160 ms
    depois desse calculo, entao encostar um keep no inicio de um cue vizinho
    ainda e arriscado — deixe folga.
18. **`cropx_timeline` tambem existe aqui.** Este motor aceita
    `cropx_timeline: [[tempo_no_fonte, cropx], ...]` por clipe, portado da
    `bombordo-boreste`. Use sempre que a gravacao alternar close e plano aberto:
    com recorte fixo, o plano aberto vira um enquadramento da mesa. Gere a lista
    com o `face_crop.py` e confira que cada mudanca coincide com um corte de
    camera.


## Caption rhythm: never drop a block

`plan.py` runs a `ritmo()` pass over the finished captions. A one-word block with
0.15 s reaches 60 characters per second and reads as a flash, not a caption. The
pass tries, in order: stretch into the silence that follows (free), borrow time
from the next block and then the previous one (only costs if they are tight too),
and merge as a last resort (it fattens the line).

**Dropping a block is never an option.** The old code ended with
`out=[o for o in out if o['e']-o['s']>0.18]`, which silently deleted captions the
de-overlap step had squeezed to nothing — in real material that removed a whole
spoken sentence from the screen and left an orphan word behind, with nothing in
any report to show it had happened. Squeezed blocks now merge into the neighbour
instead.

Tunable with `MIN_BLOCK` (0.45 s), `MAX_CPS` (20) and `MAX_MERGE_CHARS` (30).

The pass cannot fix everything, and it should not pretend to. When the speaker
talks faster than the reading limit and no neighbour has slack, a block stays
above 32 CPS. That is a case for `caption-quality-gate` to flag and for a human
to decide — better a flagged fast caption than a mutilated sentence.

## Film burn on the way out

`render.py` screen-blends the film burn at the head of every clip. Setting
`BURN_OUT` to a number of seconds also blends a second copy so its flare lands at
the very end, which closes the clip instead of letting it just stop. The asset
peaks 0.53 s in, so `BURN_OUT=0.63` puts the peak on the last frame.

**It ships off (`BURN_OUT=0`) on purpose.** This skill is the engine behind
several clients; turning an outro burn on by default would change the delivered
look for clients who never asked for it. Each client skill opts in.

## Rules that matter

- **Captions align on a shared baseline.** Words are positioned by font ascent, never
  by their own bounding box — otherwise `o`, `aí`, `É` float up and the line looks
  crooked. Emphasis words are larger but sit on the same baseline.
- **≤18 characters** per caption, auto-wrapped to two lines and auto-shrunk to fit.
- **Fix the Portuguese.** Auto-transcribed SRTs mangle jargon. Put regex→replacement
  pairs in `job.fix`; they run *after* cues are merged, so multi-word fixes work.
- **Emphasis** words come from `job.emph` (space-separated, matched case- and
  punctuation-insensitively).
- **Alpha in ffmpeg:** this build's `libvpx-vp9` silently drops alpha and `qtrle`/PNG
  MOVs are huge. Ship colour + `alphaextract` matte as two H.264 files and
  `alphamerge` them at compose time.
- **`blend=all_mode=screen` must run in RGB.** Screening YUV planes tints the whole
  frame magenta — `format=gbrp` both inputs first.
- **Fixed crop per clip.** `cropx` is the horizontal centre (0–1) of the 608×1080
  window; set it per clip so an off-centre speaker isn't clipped.

## Where to render

Caption bands, clicks, film burn and covers are cheap — do them anywhere. The h264
encodes are the slow part; on a 2-core sandbox a 45 s clip costs ~2 min end to end.
If the user's machine is reachable, run the encodes there instead. Keep an eye on
delivery limits: files over ~20 MB can't be written back to a connected folder, so
either render on the device or cap the bitrate (`crf 24`, `maxrate 2900k` lands a
47 s 1080×1920 clip at ~18 MB).

## Music

`render.py`'s `final()` mixes background music automatically when a clip sets
`"music"` (path to the track) and optionally `"mix"` (`music_db` default -26,
`music_offset` seconds into the track to start from, `duck_threshold`/`duck_ratio`
for the sidechain duck against dialogue, both with sane defaults). Use the
`talking-head-music` skill to shortlist and pick the track and offset per clip
first — don't default to 0:00 or the first file in a folder. Aggregator downloads
(Pixabay, Mixkit, etc.) are blocked from the sandbox; pick from an approved local
library instead.

## Deliverables

`outdir/<clip>.mp4` (1 s cover + film burn + clip) and `outdir/capa_<clip>.png`.
Also hand back the DaVinci `HH:MM:SS:FF` in/out of each source window so the editor
can find the moment in the master.

## Zoom suave e cortes de gaguejada (aprendido em fernanda-produto)

Padrão de movimento aprovado pelo usuário ("esse zoom ficou muito bom"). Vale propagar para as skills que usam este motor, respeitando a identidade de cada cliente:

- **Zoom de ênfase:** entra em 0,6 s (ease in-out senoidal, +12%) e volta em 4 s, a cada 10–18 s, no começo de frase, só com o falante em tela cheia. Entrada de 0,25 s foi reprovada como "rápida demais".
- **Centralização:** use crop dinâmico (`crop=w='W/z':h='H/z':x='(W-W/z)/2':y='(H-H/z)*0.38'`) e depois `scale` fixo. `scale(eval=frame)` + `crop=...:'(iw-W)/2'` usa o `iw` da configuração inicial e ancora o zoom no canto: o falante "escorrega" e o zoom parece ir para a esquerda.
- **Vários zooms:** combine os termos com `max()`. Somar termos que se sobrepõem dobra o zoom.
- **Corte de gaguejada:** corte de silêncio a silêncio medido no envelope do áudio em passos de 10 ms, não pelos tempos de palavra do Whisper, que deixaram meia sílaba ("q-que"). Esconda o jump cut com um zoom seco de +10% que volta em 3 s. Transcreva o trecho cortado de novo antes do render.
- **Transições:** coloque entrada e saída de B-roll, burn e SFX no centro de uma pausa real da fala. Um flash com whoosh sobre a palavra retomada soou como "corte cortando palavras". Ferramenta de referência: `fernanda-produto/scripts/find_pauses.py`.
