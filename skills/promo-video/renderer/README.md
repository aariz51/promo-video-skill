# renderer

The Remotion project that renders every `/promo-video` film. It is data-driven: the only
input is `render-config.json` (compiled by `promo compile` from a product's
`timeline.json`) plus a staged public folder with the product's assets and audio master.
You do not edit this project per product.

```
src/
  Root.tsx          three compositions: Promo16x9 (master), Promo9x16, Promo1x1
  Film.tsx          lays the scenes on the clock from render-config.json
  transitions.tsx   fade · light · push · zoom · wipe · cut, plus a constant camera drift
  layout.ts         u-units, aspect detection, fitSize()
  style.tsx         resolved colours from the config
  scenes/           the thirteen primitives (hook, wordzoom, title, statement, pillars, screen, flow,
                    terminal, document, montage, compare, metric, lockup)
  components/       Atmosphere (ground, grain, point of light), DeviceFrame, GlassCard,
                    KineticWords, Cursor, Bloom, Whoosh, Particles, FontLoader
  animations/       springs, easings, motion helpers, cube.tsx (Cube Motion bridge)
  sample/           sample props so `npx remotion studio` opens without a product
public/fonts, public/sfx
```

```bash
npm ci
npx remotion studio         # preview with the sample props
npx tsc --noEmit
```

Renders are normally driven by `promo render`, which runs
`npx remotion render src/index.ts <composition> <out> --props=<render-props.json> --public-dir=<stage>`.
