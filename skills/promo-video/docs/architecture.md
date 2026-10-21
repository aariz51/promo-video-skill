# Architecture

`/promo-video` is a **creative compiler**. Two inputs, the product and an optional
inspiration video, are compiled through written intermediate artifacts into a film. The
agent does the judgement (understanding, analysis, direction); the engine does everything
that must be exact (validation, scheduling, sound, rendering, QA).

```
PRODUCT REPOSITORY            OPTIONAL YOUTUBE INSPIRATION
        │                                 │
   L2 analyzer.py                    L3 watcher.py ── claude-video `watch`
   product-scan.json                 inspiration/evidence.json, pacing.json
        │ (agent reads source)            │ (agent reads every frame)
   product-brief.md              L4 inspiration-analysis.md  ◀─ or MASTER CREATIVE FRAMEWORK
        └──────────────┬──────────────────┘
                 L5 adapter.py  →  creative-prompt.md   (agent completes)
                       │
                 L6 timeline.json (agent) → timeline.py → render-config.json, storyboard.md, narration.txt
                       │
          voiceover.py → audio.py (effects + voice, no music) → L7 render.py (Remotion)
                       │
                 L8 qa.py → qa-report.md, qa/frames/
```

| Layer | Code | Responsibility |
|---|---|---|
| 1 Command | `SKILL.md` | conversation: one question, then the workflow |
| 2 Product analyzer | `engine/promo_engine/analyzer.py`, `capture.py` | repo map with evidence paths; launch + screenshot the real product; never reads secrets |
| 3 Video watcher | `watcher.py` | runs the installed `watch` skill, parses its report, measures hard cuts |
| 4 Creative analyzer | `artifacts.py` (`check_inspiration`) | holds the YOUTUBE INSPIRATIONAL PROMPT to its twelve-section contract; rejects copied narration |
| 5 Creative adapter | `adapter.py`, `artifacts.py` (`check_creative`) | source rules → CREATIVE DNA; source scenes rescaled to the runtime; validation against brief and source |
| 6 Timeline engine | `timeline.py`, `sound.py` | schema, fact checks, event scheduling, sound cues, storyboard |
| 7 Renderer | `render.py` + `renderer/` (Remotion) | stages assets, renders each aspect from the same props |
| 8 QA | `qa.py` | file, timing, narration and no-music checks; per-scene stills |

## Why these boundaries

- **Artifacts, not memory.** Every decision is a file. A bad film can be traced to the
  artifact that caused it and fixed there.
- **The renderer never invents timing.** `timeline.py` schedules every event (`props._t`)
  and derives sound cues from the same numbers. Picture and sound cannot drift apart.
- **One renderer for every product.** Scenes are parameterised primitives reading
  `render-config.json`; product assets arrive through a staged `--public-dir`. Nothing is
  copied into the product repo except the `promo/` workspace.
- **Layout abstraction.** Scenes size in `u` (1% of the short side) and branch on aspect
  (`layout.ts`), so 9:16 and 1:1 reuse the same scenes and the same timeline.
- **Determinism.** No `Math.random`, no wall clock. Scatter comes from `seed`. The same
  timeline gives the same frames; the same voice takes are cached.
- **Honesty is enforced, not requested.** Claims cite files that must exist; numbers need
  claim ids; metric scenes need sources; copied inspiration wording fails checks; music
  cannot enter the mix and QA proves its absence.

## Motion layers

Cinematic motion (cameras, devices, light, orbits) uses Remotion springs and
`interpolate` (`animations/springs.ts`, `easings.ts`, `motion.ts`). UI and typography
motion (lists, captions, labels) uses [Cube Motion](https://www.cube-motion.dev) through
`animations/cube.tsx`, which pauses its Web Animations and seeks them to the Remotion
frame so they stay frame-accurate. Never import `cube-motion` directly in a scene.
