# promo-video

**An agent skill that turns your repository into a cinematic product film.**

Run `/promo-video` in any product's repository. The agent inspects the codebase to
understand what the product does and which moments are worth showing, optionally watches a
YouTube video you like for its creative language, writes a product-specific creative brief
from the two, and renders an original 1920×1080 launch film in [Remotion](https://remotion.dev):
real product moments, sparse voiceover, sound design, no background music, and an automated
QA pass. It works for web apps, SaaS, mobile apps, AI products, developer tools and CLIs.

```
PRODUCT REPOSITORY  +  OPTIONAL YOUTUBE INSPIRATION
        ↓                         ↓
  product brief        YOUTUBE INSPIRATIONAL PROMPT  (or the master creative framework)
        └───────────┬─────────────┘
       PRODUCT-SPECIFIC PROMO PROMPT
                    ↓
     storyboard → timeline → motion → voiceover + sound → render → QA → film
```

---

## Installation

Requirements: Python ≥ 3.11, Node ≥ 18, `ffmpeg`/`ffprobe`. For the inspiration workflow,
also `yt-dlp` and the [`watch`](https://github.com/bradautomates/claude-video) skill.

```bash
git clone https://github.com/aariz51/promo-video-skill.git
cp -r promo-video-skill/skills/promo-video ~/.claude/skills/promo-video      # Claude Code
# or: cp -r promo-video-skill/skills/promo-video ~/.codex/skills/promo-video # Codex

# the renderer's dependencies (installed automatically on first render if you skip this)
cd ~/.claude/skills/promo-video/renderer && npm ci

# only for the inspiration workflow
brew install yt-dlp          # or: pip install yt-dlp
# in Claude Code:
#   /plugin marketplace add bradautomates/claude-video
#   /plugin install watch@claude-video
# or any Agent Skills host:
npx skills add bradautomates/claude-video -g
```

Check the setup: `python3 ~/.claude/skills/promo-video/bin/promo doctor`.

## Usage

Open your product's repository in Claude Code and run:

```text
/promo-video
```

The agent asks one question:

> **Do you have a YouTube video you want to use as visual inspiration?**
> Yes, I have an inspiration video · No, create the creative direction yourself

Everything else (name, features, audience, colours, screens) comes from the repository.
You can also pass the URL directly: `/promo-video https://youtu.be/…`.

## Inspiration workflow

1. The `watch` skill downloads the video and extracts scene-aware frames and a
   timestamped transcript; the engine measures every hard cut.
2. The agent reads every frame and writes a **YOUTUBE INSPIRATIONAL PROMPT**: twelve
   sections from video identity and hook analysis to a timestamped story structure,
   pacing, motion, visual, sound, narration, typography and transition systems, the
   cinematic arc, and 10–20 reusable creative rules.
3. It inspects the product and writes a **PRODUCT PROMO BRIEF** in which every factual
   claim cites the file that supports it.
4. `promo adapt` rescales the inspiration's structure and pacing to the target runtime
   and carries its rules forward; the agent fills in the product and writes the
   **PRODUCT-SPECIFIC PROMO PROMPT**.
5. The prompt becomes a timeline, then a rendered and verified film.

## No-inspiration workflow

Without a video, the **master creative framework**
([`framework/master-creative-framework.md`](skills/promo-video/framework/master-creative-framework.md))
is the creative source: a 13-beat launch-film arc (hook → title → shape of the product →
proof → hero demonstration → … → final lockup), pacing rules, show-don't-tell patterns,
visual, motion, typography, sound and narration systems, and accuracy rules. The agent
keeps the beats the product can support truthfully and adapts them the same way.

## Architecture

| Layer | Where | Job |
|---|---|---|
| 1 Command | `SKILL.md` | one question, then the workflow |
| 2 Product analyzer | `engine/…/analyzer.py`, `capture.py` | repo map with evidence; launches and screenshots the real product |
| 3 Video watcher | `watcher.py` | wraps the `watch` skill; measures cuts |
| 4 Creative analyzer | `artifacts.py` | the inspiration prompt's contract |
| 5 Creative adapter | `adapter.py` | source + brief → product-specific prompt |
| 6 Timeline engine | `timeline.py`, `sound.py` | validation, fact checks, event and sound scheduling |
| 7 Renderer | `render.py`, `renderer/` | one Remotion project, thirteen scene primitives, three aspect ratios |
| 8 QA | `qa.py` | file, timing, narration and no-music checks; per-scene stills |

Every step writes an inspectable artifact to `promo/` in your repository:

```text
promo/
  promo.config.json        product-scan.json        product-brief.md
  inspiration/             inspiration-analysis.md  creative-prompt.md
  timeline.json            storyboard.md            narration.txt
  render-config.json       out/promo-16x9.mp4       qa-report.md   qa/frames/
```

See [`docs/architecture.md`](skills/promo-video/docs/architecture.md).

## Configuration

`promo/promo.config.json` (created by `promo init`; every field is optional):

```json
{
  "product": { "name": "Tallyboard", "description": null, "root": ".." },
  "inspiration": { "url": "https://www.youtube.com/watch?v=…" },
  "duration": { "min": 60, "max": 100 },
  "format": { "aspects": ["16:9"], "fps": 30 },
  "style": { "preset": "graphite", "accent": "#1F8A70" },
  "voice": { "provider": "auto", "voice": null, "direction": "Calm, confident, precise." },
  "sound": { "ambience": false },
  "render": { "quality": "final", "outputDir": "out" },
  "seed": 1
}
```

| Environment variable | Used for |
|---|---|
| `OPENROUTER_API_KEY` | optional: OpenRouter voiceover (read from the environment only, never logged) |
| `PROMO_WATCH_SKILL_DIR` | optional: where the `watch` skill lives, if not in a standard location |
| `PROMO_CHROME` | optional: the Chrome/Chromium binary used to capture the product |

The `watch` skill keeps its own optional Whisper keys in `~/.config/watch/.env`.

## Rendering

```bash
promo build                          # compile → voice → audio → render → qa
promo render --quality draft         # half-resolution preview
promo render --aspect 9:16 --aspect 1:1
```

(`promo` = `python3 <skill>/bin/promo`.) Output goes to `promo/out/`. The renderer is a
single Remotion project inside the skill; product assets reach it through a staged public
folder, so nothing is copied into your repository except the `promo/` workspace. Open
`npx remotion studio` in `renderer/` to preview the primitives with sample props.

## Voiceover

Sparse voiceover is on by default. The provider is configurable: OpenRouter's
`gpt-audio` when `OPENROUTER_API_KEY` is set, macOS `say` offline, your own recordings,
or none (only with a stated reason). Every take is checked against its script, and a line
that cannot fit its scene stops the build instead of being rushed.
See [`docs/voiceover.md`](skills/promo-video/docs/voiceover.md).

## Audio

**No background music by default, or ever.** The mix contains only short sound effects
tied to on-screen events, the voiceover, silence and, if you enable it, a non-melodic
ambience bed. QA proves it: it checks every source in the mix and measures that the
master is near-silent wherever no effect or voice line is sounding.

## Creative originality

An inspiration video is analysed for its *grammar* (pacing, structure, motion,
typography, transitions, sound philosophy) and never cloned. No footage, logos, graphics,
wording or narration is reused. The validators reject any seven-word run copied from the
video's transcript in the analysis, the creative prompt or the narration, and the scene
content always comes from your product.

## Factual accuracy

Every on-screen or spoken fact traces to a claim in the brief, and every claim cites a file
in your repository that must exist. Numbers without a claim id, metrics without a source,
and claims pointing to missing files all fail validation.

## Contributing

- **Analyzers:** extend `analyzer.py` (new manifest types, routers, design-token sources).
- **Creative templates:** frameworks and artifact contracts live in `framework/`;
  validators in `artifacts.py`.
- **Motion primitives:** add a kind in `timeline.py`, its cues in `sound.py`, its scene in
  `renderer/src/scenes/`; see [`docs/motion-language.md`](skills/promo-video/docs/motion-language.md).
- **Renderers:** `render.py` takes `render-config.json` and a staged public folder; another
  backend can consume the same contract.
- **QA modules:** add a check in `qa.py` and a test in `tests/`.

Run the tests with `python3 -m unittest discover -s tests` (add `PROMO_E2E=1` to render a
real film), and `npx tsc --noEmit` in `renderer/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Example

[`examples/self-promo/`](examples/self-promo) holds every artifact from running the skill
on this repository: scan, brief, creative prompt, timeline, storyboard, narration and QA
report.

## Credits and licences

- [Remotion](https://remotion.dev): check its licence for commercial use.
- [Cube Motion](https://www.cube-motion.dev) (`cube-motion`, MIT) for UI and type motion.
- [`claude-video` / `watch`](https://github.com/bradautomates/claude-video) (MIT) for video analysis.
- Fonts: Inter and JetBrains Mono (SIL Open Font License).
- Bundled sound effects are placeholders: verify their licensing before commercial use,
  or replace them. See [NOTICE](NOTICE).

MIT © 2026 Aariz Rasheed. See [LICENSE](LICENSE).
