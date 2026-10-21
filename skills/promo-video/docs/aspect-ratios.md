# Aspect ratios

The master is **1920×1080 (16:9)**. The same `timeline.json` renders at:

| Aspect | Composition | Size | Command |
|---|---|---|---|
| 16:9 | `Promo16x9` | 1920×1080 | `promo render` (default) |
| 9:16 | `Promo9x16` | 1080×1920 | `promo render --aspect 9:16` |
| 1:1 | `Promo1x1` | 1080×1080 | `promo render --aspect 1:1` |
| store-portrait | `PromoStorePortrait` | 886×1920 | `promo render --aspect store-portrait` |
| store-landscape | `PromoStoreLandscape` | 1920×886 | `promo render --aspect store-landscape` |

Choose formats once with `promo init --formats 16:9 store-portrait …`; only those are
rendered. Draft renders are half size, except the App Store sizes (886 / 2 is odd, which
H.264 cannot encode), which render drafts at full size.

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

App Store previews must be 15–30 s at the device's exact size (886×1920 or 1920×886
for the 6.5" iPhone). Make a separate workspace with `promo init --runtime 15-30 --formats
store-portrait` and a short timeline rather than speeding up the master.
