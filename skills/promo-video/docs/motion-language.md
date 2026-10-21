# Motion language

How the primitives move, and the rules to keep if you add one. The creative source
(framework or inspiration prompt) decides *which* motion a film uses; these rules decide
how it is built.

## Principles

- **Springs, not linear moves.** Entrances use the shared presets in
  `animations/springs.ts`: `sEnter` (confident reveal), `sPop` (punchy), `sSettle`
  (heavy, premium), `sBounce` (delight). A bespoke curve is what makes one scene feel
  bolted on.
- **One curve vocabulary.** `animations/easings.ts`: `EASE.out`, `inOut`, `in`, `soft`.
- **The camera moves with intent.** Push-in to build importance, pan to connect, pull to
  reveal scale, rise to present. Every scene also drifts ~3% so nothing is dead-still
  unless stillness is the point (the hook's freeze).
- **One focal subject per frame.** Negative space is how importance is signalled.
- **Transitions are ideas.** `light` for act breaks, `push`/`zoom` into detail, `wipe` for
  typographic changes, `cut` inside fast sections, `fade` as the quiet default.
- **Idle life is seeded.** `motion.ts` gives `bob`, `sway`, `pulse`, and `seed(i)` for
  deterministic scatter. Never `Math.random`.

## Two layers

| Layer | Tools | For |
|---|---|---|
| Cinematic | springs, `interpolate`, CSS 3D | devices, cameras, light, orbits, fragments |
| UI and typography | Cube Motion via `animations/cube.tsx` | lists, captions, labels, text that changes state |

Cube Motion (`rise`, `leave`, `morph`) runs on the Web Animations API in wall-clock time.
The bridge pauses each animation and seeks it to `(frame − at) / fps`, so the library
keeps its curves and staggers and Remotion keeps the clock. `at` is a frame inside the
enclosing `<Sequence>`. Render with `--props` containing `"cube": false` to see exactly
what the layer contributes.

## Typography

- Inter for statements and UI; JetBrains Mono for machine output, data and eyebrows.
- Headlines are rare and large, built word by word (`KineticWords`), with accent words
  coloured instead of resized.
- `fitSize()` guarantees text fits its box at every aspect; the engine also caps lengths.

## Adding a primitive

1. Add the kind, its required props and text limits to `KINDS` in `engine/promo_engine/timeline.py`.
2. Schedule its events in `_schedule()` (seconds, scene-relative) and give it cues in `sound.py`.
3. Write `renderer/src/scenes/<Name>.tsx`: read `scene.props._t`, size in `useLayout().u`,
   branch on `aspect`, use the shared springs, no randomness.
4. Register it in `renderer/src/scenes/index.tsx`. `tests/test_pipeline.py` checks the
   engine and renderer agree.
5. Document its props in `docs/timeline.md`.
