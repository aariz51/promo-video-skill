# Architecture

`/promo-video` is a **creative compiler**. The product and an optional reference video are
compiled through written, validated artifacts into a verified film. The agent does the
judgement (understanding, direction, writing); the engine does everything that must be
exact (mode and audio policy, measurement, validation, scheduling, sound, rendering, QA).

```
INPUT ──▶ init / questions: mode from the input, audio policy {voiceover, soundEffects, music:false}
          │
PRODUCT REPOSITORY                         REFERENCE VIDEO (Mode B only)
   analyzer.py → product-scan.json            watcher.py ── claude-video `watch` (transcript, frames)
   (agent reads source, captures)             reference.py → reference/breakdown.json, motion-spec.json,
   product-brief.md  ── check brief                         frames/, sheets/   (measured from pixels)
                                              direction.py → CREATIVE_DIRECTION.md ── check direction
          └──────────────────┬───────────────────────┘
                 adapter.py → creative-prompt.md ── check creative
                             (Mode A: framework arc scaled to runtime · Mode B: measured scenes + rules)
                             │
                 timeline.json  (Mode B: `promo storyboard` skeleton with the reference's structure)
                 timeline.py ── check timeline (Mode B: direction.structure_check)
                             → render-config.json (+ audioPolicy), storyboard.md, narration.txt
                             │                   (Mode A: CREATIVE_DIRECTION.md from the prompt)
          voiceover.py (voice-over mode only) → audio.py (synthesised effects; none when silent)
                             │
                 render.py (Remotion; --muted when silent) → out/*.mp4
                             │
                 qa.py → TEST_REPORT.md, qa/validation.json, qa/frames/
                             │
                 deliver.py → deliver/ (films, direction, reports, evidence, editable remotion/)
```

| Module | Responsibility |
|---|---|
| `config.py` | workspace layout; the run config, its validation (music can only be `false`), formats and render scale |
| `reference_input.py` | the mode from the input: none, YouTube, other URL, or a probed local video |
| `questions.py` | the opening questions still open; never re-asks a decided one |
| `providers.py` | voice provider resolution; ambiguity and absence become questions, never a silent swap |
| `analyzer.py`, `capture.py` | product map with evidence paths; screenshots of the running product; never reads secrets |
| `watcher.py` | runs the `watch` skill, degrades honestly when it is missing or broken, reuses downloads |
| `reference.py` | metadata, boundaries and transition types, camera estimate, colour, evidence, contact sheets, motion spec, fingerprint cache; also verifies our own films' planned transitions |
| `direction.py` | CREATIVE_DIRECTION.md scaffold and check; reference-derived storyboard; structural fidelity check; Mode A direction |
| `artifacts.py`, `adapter.py` | brief and creative-prompt contracts; the creative-prompt scaffold |
| `timeline.py`, `sound.py` | schema, fact checks, event scheduling, sound cues, the audio policy in the render config |
| `sfx_synth.py` | the effect library, synthesised from formulas (licence-clean, byte-reproducible) |
| `voiceover.py` | OpenRouter / OpenAI / `say` / files; take verification, bounded retry, input-keyed cache, redaction |
| `audio.py` | the mix per policy; audio-manifest.json records every source |
| `render.py` | stages assets, renders each format from the same props |
| `qa.py` | encoded-file checks, audio per mode, motion and transitions measured in the file, Mode B fidelity |
| `deliver.py` | the delivery folder and the ejected, editable Remotion project |

## Why these boundaries

- **Artifacts, not memory.** Every decision is a file; a bad film traces back to the artifact
  that caused it.
- **Measured, not described.** In Mode B the reference's scenes, transitions and camera moves
  are measured from its pixels; the agent adds what pixels cannot say, beside the evidence.
- **The reference drives the build.** The storyboard is derived from the breakdown and the
  timeline check holds the film to it; departures must be written down.
- **The renderer never invents timing.** `timeline.py` schedules every event; picture and
  sound share one clock. Transitions play over the incoming scene's first frames, so a scene
  starts where the reference's transition into it starts.
- **One audio policy.** Set once, carried in `render-config.json`, obeyed by voice, mix, render
  and QA. Music has no code path.
- **Verification is measurement.** QA decodes the films and measures them against the plan;
  a process exit code proves nothing.

## Motion layers

Cinematic motion (cameras, devices, light, orbits) uses Remotion springs and `interpolate`.
UI and typography motion uses [Cube Motion](https://www.cube-motion.dev) through
`animations/cube.tsx`, which pauses its Web Animations and seeks them to the Remotion frame
so they stay frame-accurate. Never import `cube-motion` directly in a scene.

## Known limits

- Pixel analysis cannot separate a fade into an *empty* frame from a text reveal, or a
  classic push from a camera pan; these read as the simpler interpretation. A sparse, dark
  wipe can fall below a blind pass's threshold; the planned-window check in QA still
  measures it.
- The installed claude-video `watch` 0.2.0 passes `-vsync`, which ffmpeg 7+ removed; its
  frame extraction fails there. `promo watch` then keeps its transcript and measures the
  frames itself, and the evidence says so.
