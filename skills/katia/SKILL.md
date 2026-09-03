---
name: katia
description: Crie cortes verticais 9:16 para Reels, TikTok e Shorts da Katia, usando o estilo, a fonte e a trilha próprios desta cliente. Use somente em trabalhos da Katia.
---

# Katia → Reels

**Local setup:** dependencies (Pillow, numpy) live in a venv at
`~/.claude/skills/katia/.venv`. Run scripts with
`~/.claude/skills/katia/.venv/bin/python3 scripts/make_reels.py`, or
`source ~/.claude/skills/katia/.venv/bin/activate` first, instead of the
bare `python3` shown below. Requires `ffmpeg`/`ffprobe` on PATH (already present
via Homebrew).

Builds finished vertical cuts from a master video + SRT. Everything is driven by one
`job.json`; the scripts do transcription-free caption timing (reused from the SRT),
silence-snapped trimming, caption rendering, audio sweetening and the cover. Forked
from `podcast-reels` for this client — same engine, Katia-specific defaults below.

## Katia — client defaults

- **Caption + cover font:** Montserrat Bold (`assets/Montserrat-VariableFont_wght.ttf`,
  variable font — `render_caps.py`/`cover.py` call `set_variation_by_name('Bold')`,
  override with `FONT_WEIGHT` env if a different weight is ever needed). Set
  `"font"` in `job.json` to this path; do not fall back to the bundled CalSans.
- **Cover layout:** headline sits lower on the frame than the shared default
  (`y = int(H*0.775) - total//2` in `cover.py`, vs `0.735` upstream) and has **no**
  blue accent bar above it — Katia's cover is just scrim + headline + optional logo.
  Don't reintroduce the bar; it was removed on purpose for this client.
- **Framing:** static single-camera talking-head recordings, but don't guess one
  `cropx` for the whole batch — a single eyeballed value (e.g. `0.58`) drifted
  0.05–0.13 off-center across the 8 reference clips because framing shifts
  slightly between recording moments even on the "same" camera. Run
  `scripts/face_crop.py --job job.json --clip <k> --out ... --preview ...` per
  clip and use `timeline[0][1]` as that clip's `cropx` (a single-shot talking
  head returns one timeline entry — no need for `cropx_timeline` plumbing here).
  Always eyeball the `--preview` image before trusting it.
- **Music:** pull from the shared library at
  `/Volumes/SSD/Movies/Edição/Mídia/gravaçõesSEBRAE/content_hub_assets/music/`
  (yes, that's the Content Hub/SEBRAE asset pool — it's a shared, license-cleared
  music pool, safe to reuse across clients) via the `talking-head-music` skill's
  workflow. Katia's content is reflective/empowering monologues, not corporate hype —
  favor warm, low-key, piano/string tracks (e.g. `piano_reflections_ahjay_stelino`,
  `your_breath_eugenio_mininni`, `better_times_are_coming_alejandro_magana`) over the
  driving/motivational-business tracks in that pool, and vary the offset per clip.
- **Cuts:** Katia's raw recordings are multi-take — she repeats the same scripted
  monologue several times until a take is approved (listen for restart cues like
  "volta", "de novo", "3, 2, 1" and an explicit "gostei"/approval after a clean take).
  Always cut from the last clean, approved take, never an earlier rehearsal.

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
