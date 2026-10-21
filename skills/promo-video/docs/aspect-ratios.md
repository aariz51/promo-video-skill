# Aspect ratios

The master is **1920×1080 (16:9)**. The same `timeline.json` renders at:

| Aspect | Composition | Size | Command |
|---|---|---|---|
| 16:9 | `Promo16x9` | 1920×1080 | `promo render` (default) |
| 9:16 | `Promo9x16` | 1080×1920 | `promo render --aspect 9:16` |
| 1:1 | `Promo1x1` | 1080×1080 | `promo render --aspect 1:1` |

To render all three every time, set `"format": {"aspects": ["16:9", "9:16", "1:1"]}` in
`promo.config.json`.

## How scenes adapt

Scenes never use raw pixels. `renderer/src/layout.ts` gives each scene:

- `u`: 1% of the frame's short side, the unit for type, spacing and radii;
- `aspect`: `landscape` | `portrait` | `square`, and `wide` for side-by-side layouts;
- safe margins, and `fitSize()`, which shrinks a line until it fits its box and line budget.

Landscape spreads (columns, device beside copy); portrait stacks (rows, device centred);
square uses the stacked layout with tighter margins. Timing is identical in every aspect,
so one audio master serves all of them.

## When to write a separate timeline

If a vertical cut needs a genuinely different story (shorter, different hero), copy
`timeline.json` to a new workspace and edit it. The primitives stay the same.

## Store previews

App Store previews must be 15–30 s at the device's exact size. Make a separate workspace
with `"duration": {"min": 15, "max": 30}` and a short timeline rather than speeding up the
master.
