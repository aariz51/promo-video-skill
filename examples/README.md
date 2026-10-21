# Examples

Two real runs of `/promo-video` on this repository. Same product and brief, different
creative source, so the films differ in structure, not just in colour.

| | `self-promo/` (no inspiration) | `self-promo-inspired/` (YouTube inspiration) |
|---|---|---|
| Creative source | master creative framework | `youtu.be/9sMVY15d7BA`, analysed with `watch` |
| Runtime | 93 s, 11 scenes | 67 s, 8 scenes |
| Ground | graphite | paper, with a blue brand ground |
| Opening | repository fragments orbit a point of light, freeze, a question | a small typed line; cursors select a word; fly through its letter into the brand |
| Cuts | a fade, push, light and wipe vocabulary | continuous travel; hard cuts only at the two turns, as in the reference |

Each folder holds every artifact the pipeline produced: `product-scan.json`,
`product-brief.md`, (`inspiration-analysis.md`, `inspiration/pacing.json`),
`creative-prompt.md`, `timeline.json`, `storyboard.md`, `narration.txt`,
`render-config.json` and `qa-report.md`.

Not committed: rendered films, audio, QA stills (regenerate with `promo build`), and the
inspiration's `evidence.json`/`watch-report.md`, which contain the source video's caption
transcript (regenerate with `promo watch https://youtu.be/9sMVY15d7BA`).

To rebuild either film from the repository root:

```bash
python3 skills/promo-video/bin/promo -w examples/self-promo build
```
