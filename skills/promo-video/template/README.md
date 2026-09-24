# Promo film template (Remotion)

A complete, working launch-film project: 9 scenes, 4 compositions, a shared motion
vocabulary, and a keyless sound-design pipeline.

This is the infrastructure the [`promo-video` skill](../SKILL.md) scaffolds from. You can
also just use it directly as a Remotion starter.

**It renders on a fresh clone.** The shipped brand, copy, screens and logo are neutral
placeholders — replace them with yours.

## Run it

```bash
npm install
npm run dev          # Remotion Studio — scrub the timeline
npm run typecheck
```

Render:

```bash
npm run render:vertical     # 1080×1920  Reels / TikTok / Shorts / Stories
npm run render:landscape    # 1920×1080  YouTube / web hero
npm run render:store        #  886×1920  App Store preview (portrait)
npm run render:store-wide   # 1920×886   App Store preview (landscape)
```

## Make it yours

**1. `src/theme.ts` — start here.** It is the single source of truth for brand and timing.

- `COLORS` — swap for the app's real palette (sample it from the screenshots).
- `screens` — seven slots. `dashboard` is the hero/money shot in `S7_Dashboard`; the
  other six ride the orbit ring in `S6_DeviceOrbit`. Keep the key names, change the paths.
- `LOGO` — your logo, ideally square and including the wordmark.
- `T` / `dur` — scene boundaries in frames. If you change these, change `DUR` and the
  cue times in `scripts/build_audio.py` to match. They are the same timeline.

**2. Assets.** Drop PNGs into `public/app-screens/` and `public/logo/app-logo.png`,
replacing the placeholders. Screens are portrait phone captures (`SCREEN_RATIO` ≈ 0.4615);
scenes `objectFit: cover` from the top, so full-height captures look best.

To regenerate the placeholders instead: `python3 scripts/make_placeholders.py` (needs Pillow).

**3. Fonts.** `src/fonts.ts` — match the type personality of the brand.

**4. Scenes.** Rewrite the copy, the featured screens, the tagline and the logo lockup in
`src/scenes/`. The nine shipped scenes are *one worked example* — add, drop and reorder
them to suit your film (see [`../docs/scene-kit.md`](../docs/scene-kit.md)). Keep the motion language (see [`../docs/motion-language.md`](../docs/motion-language.md)):
spring-everything, float-idle, single-hero composition, light-bloom and whoosh stitches,
a cursor that presses real UI, a reward beat, a period-rhythm tagline.

**5. Audio.** Write `sound.json` — one cue per on-screen event — then:

```bash
npm run audio      # no API key, no network — ffmpeg only; no music, no bed
```

```json
{ "duration": 33, "cues": [ { "fx": "click", "at": 6.37, "vol": 1.0 } ] }
```

Effects: `click`, `pop`, `pop2`, `whoosh`, `chime`, `type`, `drag`, `sparkle`. Without
`sound.json` the built-in timeline for the nine shipped scenes is used.

**Narration (optional).** Write `voiceover.json` and run `python3 scripts/voiceover.py`
before `npm run audio`; see [`../docs/voiceover.md`](../docs/voiceover.md).

Then set `AUDIO_SRC = "audio/master.wav"` in `theme.ts`. It ships as `null` so a fresh
clone renders silently instead of failing on a master that does not exist yet.

## How it is put together

- **`Root.tsx`** registers four compositions that all render the same `Film`. Every scene
  branches on `const wide = width > height`, so portrait *stacks* and landscape *spreads*
  while the timeline stays identical — which is what lets one audio master sync to all four.
- **`animations/`** is the shared motion vocabulary: `springs.ts` (enter / pop / settle /
  bounce), `easings.ts` (one set of bezier curves), `motion.ts` (bob, sway, pulse, ramp,
  push-in, deterministic seed), and `cube.tsx` — the [Cube Motion](https://www.cube-motion.dev)
  bridge for the UI layer (`CubeRise`, `CubeList`, `CubeMorphText`…), which seeks the
  library's time-based animations to the Remotion frame. Nothing uses `Math.random()`
  or `Date` — renders must be deterministic across frames.
- **`components/`** are the reusable props: `PhoneFrame`, `GlassCard`, `Cursor`,
  `KineticWords`, `ScoreRing`, `ActionButton`, `Bloom`, `Whoosh`, `Confetti`, `Particles`,
  `FontLoader`.

## Credibility guardrails

Carried over from the skill, and worth keeping:

- Never let an overlaid number or label contradict the screenshot behind it.
- Avoid alarming empty-states in a reassurance film.
- Don't invent statistics. Prefer qualitative, on-message callouts.
- The money shot must be clean and believable — it is the spine of the film.

## Licenses

Fonts: Inter & Baloo 2 (SIL OFL). Bundled SFX are placeholders — verify their licensing
before commercial use, or replace them. Remotion has its own license terms for commercial
use; check them.
