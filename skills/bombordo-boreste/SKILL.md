---
name: bombordo-boreste
description: Crie cortes verticais 9:16 para Reels, TikTok e Shorts do podcast Bombordo e Boreste, usando o estilo, os assets e o fluxo de edição próprios deste cliente. Use somente em trabalhos do Bombordo e Boreste.
---

# Bombordo e Boreste → Reels

**Local setup:** dependencies (Pillow, numpy, OpenCV headless) live in the bundled venv at
`~/.codex/skills/bombordo-boreste/.venv`. Run scripts with
`~/.codex/skills/bombordo-boreste/.venv/bin/python3
~/.codex/skills/bombordo-boreste/scripts/make_reels.py`, or activate that venv first,
instead of the bare `python3` shown below. Requires `ffmpeg` and `ffprobe` on PATH.


Builds finished vertical cuts from a master video + SRT. Everything is driven by one
`job.json`; the scripts do transcription-free caption timing (reused from the SRT),
silence-snapped trimming, caption rendering, audio sweetening and the cover.


## Reenquadramento: um recorte por plano de camera

`face_crop.py` decide **um recorte por plano de camera**, nunca por trecho
mantido. Fechar o recorte a cada `keep` foi um bug real com defeito visivel: dois
keeps do mesmo plano recebem medianas de rosto diferentes porque o falante se
mexeu, o `cropx` pula dezenas de pixels numa emenda onde a camera nunca cortou, e
o video entregue desliza de lado. A deteccao de cena tambem roda na junção entre
dois keeps, entao um corte de camera que caiu dentro do trecho descartado
continua sendo detectado.

**Regra: `cropx` so muda onde a camera corta.** A unica excecao e trocar de
falante dentro de um plano aberto, e so quando a troca cai exatamente sobre uma
emenda que ja muda quem fala. Antes de renderizar, confira que toda mudanca de
`cropx_timeline` coincide com um corte de camera.

## O passe de ritmo das legendas

Este motor e o mesmo da `podcast-reels`, e correcoes precisam ser propagadas nos
dois sentidos. O passe `ritmo()` (blocos que piscam sao esticados, pedem tempo
emprestado ao vizinho ou fundem, e **nunca** sao descartados) veio de la; o
`cropx_timeline` foi daqui para la. O codigo antigo terminava com um
`[o for o in out if o['e']-o['s']>0.18]` que apagava em silencio legendas
espremidas pelo de-overlap, sumindo com falas inteiras sem deixar rastro em
relatorio nenhum.

## Legenda so mostra o que e ouvido

O mapeamento de cue para trecho mantido exige sobreposicao **relativa**, nao um
limiar absoluto: acima de 85% do cue o texto vai inteiro; abaixo disso vao so as
palavras proporcionais ao trecho ouvido; se nao sobra nada, o atomo e descartado.
Com o limiar absoluto antigo, 0,13 s de um cue bastavam para jogar a frase
inteira na tela com o audio dela cortado fora.


## Workflow

Before editing, read and update `references/client-content-bible.md` and `references/asset-source-catalog.md`. Use `video-project-structure` to audit the fixed project layout and prevent raw/stock media from entering Drive asset packages.

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
   `headline`, fallback `cropx`, `cover_t`, and `keeps` (list of `[start,end]` in
   *clip-local* seconds). Before rendering, generate and visually review a
   shot-aware `cropx_timeline` with `face_crop.py`; never assume one crop fits every
   camera in a clip.
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

Before accepting the last end, read at least the following 10–20 seconds of transcript
and verify that the speaker's **semantic thought** is complete. A grammatical pause or
period is not enough when the next clause qualifies, explains, or finishes the idea.
End after the complete thought, leave a short natural breath, and then start the outro;
never use the film burn to hide a sentence or context cut in half.

## What the pipeline produces

| Stage | What it does |
|---|---|
| `plan.py` | snaps keeps to silence, maps SRT cues through the trim, merges them into ≤18-char captions, flags emphasis words |
| `face_crop.py` | detects camera cuts at frame precision, samples faces with OpenCV, and emits one median crop per shot plus a visual preview |
| `render_caps.py` | draws captions to a 1080×420 band as two H.264 streams (colour + alpha matte) — fast and small |
| `clicks.py` | places a real, softly mixed shutter sample at reviewed `click_times` |
| `render.py` | cut+crop+scale with time-coded eased motion, eased zoom-out with blur opener (Python, frame-exact), screen-blends the blue film burn at both ends, overlays captions, mixes clicks/music/outro SFX, prepends the cover — **all in one x264 pass** |
| `cover.py` | grabs `cover_t`, adds scrim + headline + logo → `capa_*.png` |

Every delivered cut must have a cover. Produce both a standalone 1080×1920 PNG named
`CAPA - <headline>.png` and the same cover as the MP4's opening thumbnail frame. Before
delivery, verify that the PNG exists, inspect it visually, extract frame zero from the
MP4, and confirm that it contains the same headline treatment and logo. A rendered MP4
without this two-part cover delivery is incomplete.

The Bombordo e Boreste cover signature must be unique. Use authorized thumbnails as composition references, then compare layout, crop, typography, colours, logo and effects against the cross-client cover registry; never recycle another client's structure.

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
| framing | `cropx_timeline` (or fallback `cropx`) | everything | ~2 min |
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

For framing, run the dedicated analyser and inspect its full-height preview:

```bash
python3 scripts/face_crop.py --job job.json --clip corte01 \
  --out work/face_corte01.json --preview work/face_corte01.jpg
```

Copy the reviewed `timeline` into `job.clips.<clip>.cropx_timeline`. Detection is a
proposal, not permission to skip visual review.

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
8. **Motion feels twitchy.** Do not reset a zoom at every edit. Place
   `impact_pulses` on meaningful words and give them about 0.9–1.2 s with a modest
   4–5.5% amplitude; use `long_moves` around 2.3–3.0 s for slower visual variation.
   The sine envelope starts and ends at rest. Moves below roughly 0.7 s usually read
   as a camera glitch instead of emphasis.
9. **Clicks are absent or become repetitive.** Point `CLICK` at a real sample
   (`assets/click.wav`), trim it to the transient, and define a short reviewed
   `click_times` list per clip. Two to four semantic hits usually work better than
   firing on every emphasised caption. Normalize with `CLICK_GAIN` only after trimming.
10. **Background jobs die.** On the desktop bridge each shell call is its own process
   group — `nohup`/`setsid` do not survive. Every ffmpeg call must finish inside one
   call (~45 s), so chunk long renders.
11. **Ken-burns zoom looks shaky/vibrating.** `passA`'s pre-`zoompan` oversample (`OS`/
    `OSW`) was computed from the *native crop* size (608×1080) instead of the *final
    output* size (1080×1920) — zoompan was fed a ~654×1161 source and had to do most of
    the 1080×1920 upscale itself with its own weaker scaler, which shimmers as the crop
    shifts fractionally frame to frame. Fixed: base the oversample on `W,H` so zoompan
    only ever crops and lightly downscales from an already-adequate source.
12. **A click SFX steps on the opening word.** `clicks.py` fires on every caption flagged
    `any` (emphasis), including caption 0 — if the clip's first word is in `job.emph`
    (common: it's usually the hook stat), the click lands right on top of it and sounds
    like the voice glitching. Fixed: skip `idx==0` in `clicks.build`. Emphasis styling
    (bigger text) on the opening word is still fine — only the audio click is suppressed.
13. **Face tracking causes shake or a glitch at camera changes.** Never drive the crop
    from every detected frame. `face_crop.py` locates hard cuts at frame precision and
    uses the median face centre for the whole shot. Apply changes only at those cut
    frames or existing edit boundaries. A crop that switches even 2–3 frames before
    the camera does creates a visible sideways glitch. Separate `keeps` are not
    automatically separate camera shots: if jump cuts reuse the same camera and
    composition, keep one crop across them. Re-centering every keep by a few pixels
    produces repeated lateral pulls that become more visible during zooms.
14. **Film burn fails to concatenate or stretches the frame.** Normalize the main,
    burn and generated gap to `setsar=1` before concatenating/blending. For the outro,
    reuse the burn's original audio with short fades and mix it into the last transition.
15. **Limiter unexpectedly makes everything louder.** ffmpeg's `alimiter` can
    auto-level by default. Use `level=false`; a ceiling near `0.85` leaves enough room
    for AAC conversion without true-peak clipping.
16. **"Stream specifier ':a' ... matches no streams" on the final render.** The
    bundled `filmburn_blue.mp4` is video-only — `render.final()` used to
    unconditionally reuse `[2:a]` (the burn's own audio) for the outro mix, which
    fails outright against a silent burn asset. Fixed: `render.py` now probes
    `FILMBURN` for an audio stream with `ffprobe` and only builds the burn-audio
    mix layer when one exists, otherwise skips straight to the limiter. If you
    swap in a burn asset that *does* carry its own whoosh/SFX audio, this path
    picks it up automatically — no code change needed.
17. **A long, unfragmented SRT cue ships as one on-screen wall of text.**
    `plan.py`'s caption builder only *merged* short adjacent SRT cues up to the
    18-char limit — it never *split* a cue that was already longer than that on
    its own. A fluent passage with few pauses can land as one 30-40 character
    segment, sitting motionless on screen for its whole duration instead of
    short auto-wrapped captions. Fixed: atoms longer than 18 chars are now split
    into word-packed chunks before merging, with time apportioned by character
    count across the original cue's span. Caught by `caption-quality-gate`'s
    `block_long` warning — run it on every delivered clip, not just a visual
    spot-check; this shipped on a real render (`corte02`, 19 warnings) before
    being caught here.
18. **Delivered MP4 has no colour metadata, so some players/hosts misread it as
    full-range or the wrong matrix.** `render.py` composed the final H.264 (both
    the `libx264` and `h264_videotoolbox` paths) without tagging
    `color_primaries`/`color_trc`/`colorspace`/`color_range`. Fixed: both paths
    now explicitly tag `bt709`/`tv`, and the `libx264` path also sets the
    equivalent `x264-params` (`colorprim`/`transfer`/`colormatrix`/`fullrange=off`)
    so the flag is baked into the encoded stream, not just the container header.
    Caught by `video-delivery-safety-check` — verify with `ffprobe -show_entries
    stream=color_range,color_space,color_transfer,color_primaries` on every
    delivered clip, not just a visual spot-check.

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
- **Shot-aware crop.** `cropx` is only a fallback. Prefer `cropx_timeline`, whose
  entries are `[source-local-second, cropx]`. Detect faces by shot, use a median centre
  and quantize it; do not follow normal head movement frame by frame. Confirm the
  transition frame and inspect the generated contact sheet before the full render.
- **Final burn must complete the transition.** Screen-blend it over the last 1.3–1.4 s,
  fade the composite fully to black, and hold a short black tail so the underlying
  interview frame never reappears after the burn. Keep its own sound below the
  dialogue/music mix (around −6 dB is a useful starting point).

## Where to render

Before the first render on a new machine or delivery profile, use the `video-render-optimizer` skill. Detect the GPU and FFmpeg hardware encoders, benchmark CPU versus hardware on 8–15 seconds of representative project footage, and decide using encode time, SSIM, compatibility, real bitrate and projected size. For 1080×1920/30 start around 6–8 Mb/s with a 10 Mb/s ceiling. Do not select hardware merely because it exists; reject it when it inflates bitrate or loses visible quality, and verify the final MP4 bitrate with `ffprobe`.

Caption bands, clicks, film burn and covers are cheap — do them anywhere. The h264
encodes are the slow part; on a 2-core sandbox a 45 s clip costs ~2 min end to end.
If the user's machine is reachable, run the encodes there instead. Keep an eye on
delivery limits: files over ~20 MB can't be written back to a connected folder, so
either render on the device or cap the bitrate (`crf 24`, `maxrate 2900k` lands a
47 s 1080×1920 clip at ~18 MB).

On Apple Silicon, `VIDEO_ENCODER=h264_videotoolbox` uses the Mac's Media Engine.
It is especially useful for review iterations; start around `VT_BITRATE=16M` for
1080×1920. On an M4 Air benchmark, a 12 s encode fell from 10.09 s with
`libx264 slow` to 2.37 s with VideoToolbox. Hardware encoding needs more bitrate
for comparable quality, so keep `libx264` as the default for compact final masters.

## Music

Use a licensed/approved track and mix it *under* the voice. Start around −21 dB and
use `sidechaincompress` keyed off the dialogue; validate by listening because masters
and musical arrangements vary. Preserve the chosen mix in `job.mix` so cache
fingerprints invalidate correctly when gain or ducking changes. A clip-level `mix`
overrides global mix fields when different masters need different gain.

## Deliverables

After every final render, run `caption-quality-gate` and `video-delivery-safety-check`; automated success never replaces visual/audio review against the job. At demand closeout, rerun `video-project-structure`, update the client bible/source catalog/manifests, and upload the required skills and reusable licensed assets to the client's Drive. Never upload raw/master/proxy or stock video to the skills/assets Drive.

`outdir/<headline>.mp4` (thumbnail frame + intro/outro film burn + clip) and
`outdir/CAPA - <headline>.png`.
Also hand back the DaVinci `HH:MM:SS:FF` in/out of each source window so the editor
can find the moment in the master.
