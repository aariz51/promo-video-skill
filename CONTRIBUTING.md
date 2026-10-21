# Contributing

Thanks for looking. The project is a creative compiler: an agent writes judgement into
artifacts, and a small engine validates, schedules, renders and verifies them. Most
contributions extend one layer.

## Where things live

| You want to… | Edit | Test with |
|---|---|---|
| Understand more kinds of products | `engine/promo_engine/analyzer.py` (manifests, routers, design tokens) | `ProductAnalysis` tests |
| Improve the default creative direction | `framework/master-creative-framework.md` | `CreativeTransformation` tests |
| Tighten an artifact contract | `framework/*.template.md` + `artifacts.py` | `InspirationPrompt`, `ProductAnalysis` |
| Add a motion primitive | `timeline.py` (`KINDS`, `_schedule`), `sound.py`, `renderer/src/scenes/`, `docs/timeline.md` | `RendererContract`, `TimelineEngine` |
| Add a QA check | `qa.py` | `QualityAssurance` |
| Support another renderer | consume `render-config.json` + the staged public dir, like `render.py` | `RenderFailures` |

See `skills/promo-video/docs/motion-language.md` for the rules a new primitive must follow
(springs, `u` units, aspect branches, no randomness, events read from `_t`).

## Ground rules

- **No product-specific content in the engine or renderer.** Real products appear only in
  a user's `promo/` workspace. A test fails on known product names.
- **Determinism.** No `Math.random`, no wall clock. Scatter comes from `seed`.
- **Honesty is enforced in code.** Don't loosen a fact or originality check to make a film
  pass; fix the timeline.
- **No music.** Don't add music files or a way to reference them.
- **Secrets.** Never read `.env` files or key files; read keys only from the environment
  and never log them.

## Developing

```bash
python3 -m unittest discover -s tests              # engine + contracts (fast)
PROMO_E2E=1 python3 -m unittest discover -s tests  # plus a real render
cd skills/promo-video/renderer && npm ci && npx tsc --noEmit
npx remotion studio                                # preview primitives with sample props
```

`SKILL.md` must stay valid against the [Agent Skills specification](https://agentskills.io/specification):
`name` matches the folder, `allowed-tools` is a space-separated string, version info lives
under `metadata`, and detailed material belongs in `docs/`.

## Licensing

By contributing you agree your work is released under the [MIT License](LICENSE). Do not
contribute audio, fonts or footage you do not have the right to relicense.
