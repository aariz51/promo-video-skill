# Promo film — Remotion template

A complete, production-ready launch-film project. The `promo-video` skill copies this,
then rewrites it for your app. You can also drive it by hand.

## Quick start

```bash
npm install
# drop your assets:
#   public/app-screens/*.png   ← your app screenshots
#   public/logo/app-logo.png   ← your logo (with wordmark)
# edit src/theme.ts            ← COLORS, `screens` map, LOGO, fonts (src/fonts.ts)
# edit src/scenes/*.tsx        ← copy, featured screens, tagline, logo lockup
npm run dev                    # preview in Remotion Studio
```

## Audio (optional)

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."   # for the AI voiceover (openai/gpt-audio, voice coral)
python3 scripts/build_audio.py             # → public/audio/master.wav
```
Edit the `VO` script and `FX` timeline in `scripts/build_audio.py`. Keep VO start times
aligned to `T` in `theme.ts`. No voiceover? Set `AUDIO_SRC = null` in `theme.ts`.

## Render

```bash
npm run render:vertical     # PromoVertical      1080×1920  → out/promo-vertical.mp4
npm run render:landscape    # PromoLandscape     1920×1080  → out/promo-landscape.mp4
npm run render:store        # PromoStorePortrait  886×1920  → out/promo-store-886x1920.mp4
npm run render:store-wide   # PromoStoreLandscape 1920×886  → out/promo-store-1920x886.mp4
npm run typecheck
```

All four compositions are the **same film** — every scene is orientation-aware
(`const wide = width > height`) and they share one audio master (timing is frame-locked
in `theme.ts`, so the prebuilt `master.wav` stays in sync).

## Structure

```
src/
├── Root.tsx            # the 4 compositions
├── Film.tsx            # master timeline: <Sequence> per scene + <Audio>
├── theme.ts            # ★ BRAND: colors, fonts, screens map, LOGO, timing (T/dur), AUDIO_SRC
├── fonts.ts            # @font-face wiring (swap the TTFs in public/fonts)
├── scenes/S1..S9.tsx   # the 9 beats — orientation-aware; rewrite copy/screens per app
├── components/         # PhoneFrame, GlassCard, Cursor, Confetti, KineticWords,
│                       #   Bloom, Whoosh, Particles, ScoreRing, ScanButton, FontLoader
└── animations/         # springs.ts, easings.ts, motion.ts — one motion vocabulary
scripts/build_audio.py  # streaming OpenRouter VO + meaningful SFX → public/audio/master.wav
public/{sfx,fonts}/     # reusable, brand-agnostic
```

## Engineering standards
Latest Remotion, React 19, strict TypeScript, 60fps. All motion is frame-derived
(`useCurrentFrame`, `interpolate`, `spring`, `Easing.bezier`) — no CSS transitions, no
`Math.random()`/`Date.now()` at render (deterministic seeded particles/confetti). Assets via
`staticFile()`. One pre-mixed audio master (avoids multi-clip stutter). See
`../docs/motion-language.md` for the design grammar.

> The shipped scenes are a **worked example** (a warm pregnancy-safety scanner) so there's
> real, premium code to adapt — replace copy, colors, screens, tagline and logo for your app.
