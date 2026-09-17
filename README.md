# promo-video-skill

**Point your coding agent at a promo video you love. Get the same motion language, rebuilt around your app.**

An [Agent Skill](https://agentskills.io) that takes a **reference video** (a YouTube URL)
and **your product's assets** (screenshots, logo, a description), reverse-engineers the
reference's creative direction — scene structure, timing, transitions, camera moves,
typography, sound design — and builds a **completely original** launch film for your
product in [Remotion](https://remotion.dev).

```
  reference video  ──▶  structural breakdown  ──▶  your assets  ──▶  original film
  (a YouTube URL)       scenes · timing            screenshots       9:16 · 16:9
                        transitions · camera       logo · colors     App Store
                        type · pacing · SFX        name · features    + sound design
```

It is not a template you fill in, and it is not a screenshot slideshow. It is a
creative-director workflow: the agent *watches* the reference, writes a real breakdown,
studies your app, writes a storyboard, then builds and renders the project.

**No API key.** If you already have Claude Code or Codex, you have everything you need.

---

## Why this exists

A good product launch film costs thousands of dollars and takes weeks, because the hard
part is not rendering video — it is **creative direction**. Knowing how fast to cut, when
to hold, how the type should land, which screen is the money shot.

Every other AI demo-video tool asks you to supply the raw material and then applies *its*
house style: avatar presenters, templated kinetic text, a screen recording with zoom
effects. You get whatever the tool's taste is.

This inverts that. **You choose the taste** by pointing at a film that already has it.
The agent does the work of understanding *why* that film works, and applies that grammar
to your product.

---

## What makes it different

| Most AI demo-video tools | This skill |
|---|---|
| Input: your recording or screenshots | Input: **a reference video** + your assets |
| Style: the tool's built-in house style | Style: **reverse-engineered from your reference** |
| Output: a rendered file | Output: a **Remotion project you own and can edit** |
| Black box | A written `CREATIVE_DIRECTION.md` showing the reasoning |

The reference is used as a **grammar, not a source**. Nothing is copied — no frames, no
footage, no audio. The skill extracts the *motion language* (spring curves, beat rate,
transition vocabulary, composition rules) and re-authors it with your brand.

---

## How it works

1. **Watch.** The [`watch` skill](https://github.com/bradautomates/claude-video) pulls
   ~30–40 frames from your reference URL. The agent reads the frames itself.
2. **Break it down.** Scene-by-scene: every transition, camera move, typography
   technique, motion principle, beats-per-second, color and light, and *why each scene
   works*.
3. **Study your app.** Every screenshot and the logo are read directly; brand colors are
   sampled from the real pixels; the money shot is identified.
4. **Direct.** Mood, palette, motion language, type, pacing — the reference's grammar
   translated into your product's world, written out as a storyboard.
5. **Build.** The Remotion template is scaffolded and customized: colors, screens, copy,
   scenes, tagline, logo lockup, and a mapped sound-design timeline.
6. **Verify and render.** Still frames are rendered at each beat and visually checked for
   collisions, overflow and off-brand color before the final renders go out.

You get a `CREATIVE_DIRECTION.md` (the full reasoning), the Remotion project, and the
rendered films.

---

## Quick start

**1. Install the video-watching engine** (this skill depends on it):

```bash
# Claude Code
/plugin marketplace add bradautomates/claude-video && /plugin install watch@claude-video

# or any Agent Skills host
npx skills add bradautomates/claude-video -g
```

**2. Install this skill:**

```bash
git clone https://github.com/aariz51/promo-video-skill.git

# Claude Code
cp -r promo-video-skill/skills/promo-video ~/.claude/skills/promo-video

# Codex
cp -r promo-video-skill/skills/promo-video ~/.codex/skills/promo-video

# or scoped to a single project
cp -r promo-video-skill/skills/promo-video /path/to/project/.claude/skills/promo-video
```

**3. Run it:**

```
/promo-video
```

Same skill, same command, both hosts. You are never asked to pick a provider or a mode.

---

## Usage

The skill asks for what it needs, in order:

```
1  Reference video   https://youtube.com/watch?v=...
2  Product name      Orbit
3  Description       "A calendar that schedules around your focus blocks."
4  Features          auto-scheduling, focus mode, team sync   (priority order)
5  Assets folder     ./assets/   (screenshots + logo)

   Deliverables      9:16, 16:9, App Store preview
```

You can also skip the questions and just say it:

> *"make me a launch video like `<url>` for my app — assets are in `./assets`"*

Then it watches, designs, builds, and renders. Expect it to take a while — the analysis
step is the point.

---

## What you get

- **`CREATIVE_DIRECTION.md`** — reference breakdown, app analysis, creative direction,
  storyboard, production plan.
- **A complete Remotion project**, customized to your brand. You own it; keep iterating
  in `npm run dev` long after the agent is done.
- **Rendered films** — 9:16 vertical (Reels/TikTok/Shorts/Stories), 16:9 landscape
  (YouTube/web), and App Store previews (886×1920 / 1920×886, ≤30s, 30fps).
- **One audio master** (sound design mapped to on-screen action) that stays
  frame-synced across every orientation. Built locally — no key, no network.

---

## Supported assets

| Asset | Notes |
|---|---|
| App / web screenshots | PNG, portrait phone captures work best (~1080×2340). Clean, real screens. |
| Logo | PNG, square, ideally with the wordmark — used in the final logo lockup. |
| Brand colors | Optional. Sampled from your screenshots if not supplied. |
| Product description | The features, in priority order. This drives the story. |
| Reference video | Any URL `yt-dlp` supports — YouTube, Loom, TikTok, Vimeo, and more. |

No assets yet? The template ships with **generated placeholder screens and a logo**, so
it renders on a fresh clone before you supply anything.

---

## Example — the same product, two different references

The clearest way to show what this skill does is to run it twice on one product and
change only the reference video.

**Product (unchanged):** a pregnancy food-and-medicine safety scanner. Same
screenshots, same logo, same feature list, same 33 seconds.

| | Reference A — a fast, gamified SaaS demo | Reference B — a calm, systems-led launch film |
|---|---|---|
| Opens on | Dark plum, brand mark glowing in | White, black type with a typewriter caret |
| Palette | Magenta / violet mesh | One accent hue on both light and dark grounds |
| Beat rate | ~1.8s — rapid, escalating | ~6s per act — slow, confident holds |
| Signature device | Hand cursor pressing real UI; a score climbing 0 → 90 | Split screen: your world light, the system's process dark, in monospace |
| Structure | **9 scenes** | **6 scenes** |
| Closes on | Logo lockup + period-rhythm tagline | Icon, then the ground inverts and the opening line's twin types in |

Same assets in. Structurally different films out — different act counts, different
grounds, different devices, different pacing. That is the whole product.

The scenes for Reference B's split screen and typewriter bookend **did not exist in the
template**; the agent wrote them because the reference called for them, and dropped the
cursor-press and confetti scenes because that reference has neither.

---

## Architecture

```
skills/promo-video/
├── SKILL.md                            # the workflow the agent follows
├── prompt/creative-director-prompt.md  # the master creative brief (parameterized)
├── docs/
│   ├── motion-language.md              # the reusable motion grammar
│   ├── scene-kit.md                    # the parts, and how to recombine them
│   ├── example-breakdown.md            # a fully worked reference breakdown
│   ├── voiceover.md                    # optional narration (not required)
│   └── appstore-cut.md                 # ≤30s / 30fps App Preview recipe
└── template/                           # a complete, working Remotion starter
    ├── src/
    │   ├── Root.tsx                    # 4 compositions (vertical/landscape/store×2)
    │   ├── theme.ts                    # ← brand + timing: the first file to edit
    │   ├── scenes/                     # 9 example scenes, all orientation-aware
    │   ├── components/                 # PhoneFrame, GlassCard, Cursor, ScoreRing …
    │   └── animations/                 # springs, easings, motion helpers
    ├── scripts/
    │   ├── build_audio.py              # mapped SFX + pad → one master (no key)
    │   └── make_placeholders.py        # regenerates the neutral placeholder assets
    └── public/{sfx,fonts,app-screens,logo}/
```

Two design decisions worth knowing:

- **One film, four sizes.** Every scene is orientation-aware (`const wide = width > height`)
  so all four compositions share one codebase, one timeline, and one audio master.
- **The template is a kit, not a mould.** Its nine scenes are one worked example. The
  agent derives *your* scene list from *your* reference — dropping scenes the reference
  does not motivate and writing new ones for its signature devices. Two different
  references produce two structurally different films.
- **Timing lives in one place.** `theme.ts` exports `T`/`dur` (scene boundaries in frames)
  and `build_audio.py` mixes against the same cues, so picture and sound stay
  frame-locked across every orientation.

---

## Requirements

| | |
|---|---|
| **Agent host** | Claude Code or Codex (both tested), or any other [Agent Skills](https://agentskills.io) host — Cursor, Copilot, VS Code, Gemini CLI, OpenCode, Goose. |
| **`watch` skill** | [`bradautomates/claude-video`](https://github.com/bradautomates/claude-video) — required, this is how the reference gets seen. |
| **Node** | ≥ 18 (Remotion) |
| **Python** | 3.x (audio builder) |
| **Binaries** | `ffmpeg`, `ffprobe` on PATH |
| **API keys** | **None.** Nothing to sign up for, nothing to configure. |

---

## Roadmap

- [ ] A `skills-ref`-based CI check so the skill stays spec-valid
- [ ] More worked reference breakdowns in `docs/` (different pacing families)
- [ ] Optional background-music bed alongside the SFX master
- [ ] Landscape-first storyboard variant (currently portrait-first, adapted)
- [ ] Example gallery: reference → generated result, side by side

## Contributing

Contributions are welcome — especially **new reference breakdowns** and **motion-language
additions**, which are the parts that compound. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits & licenses

- Built on [Remotion](https://remotion.dev) — check Remotion's own license for commercial use.
- Video analysis via [`claude-video` / `watch`](https://github.com/bradautomates/claude-video) (MIT).
- Bundled fonts: Inter & Baloo 2 (SIL Open Font License).
- Bundled SFX are placeholders — **verify their licensing before commercial use**, or replace them.

MIT © 2026 Aariz Rasheed. See [LICENSE](LICENSE).
