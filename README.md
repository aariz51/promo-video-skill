# Promo-Video — a Claude skill for premium app launch films

Turn **one reference video** + **your app's assets** into an original, cinematic
promotional film — built in [Remotion](https://remotion.dev), with AI voiceover and
mapped sound design, rendered for vertical, landscape, and the App Store.

You give it a video you love the style of (a YouTube URL) and your app (screenshots,
logo, a description). It **watches** the reference, **reverse-engineers** its motion
language, **studies** your app, then **designs and builds** a completely original launch
video in the same design family — the way a senior motion director would.

> Not a template you fill in — a creative-director workflow. It writes the storyboard,
> customizes a production-ready Remotion project to your brand, generates the voiceover
> and sound design, renders every size, and QA's the result frame by frame.

## What you get

- A `CREATIVE_DIRECTION.md` doc: reference breakdown, app analysis, creative direction, storyboard, production plan.
- A complete Remotion project customized to your brand.
- Rendered films: **9:16 vertical** (Reels/TikTok/Shorts/Stories), **16:9 landscape** (YouTube/web), and **App Store previews** (886×1920 / 1920×886, ≤30s, 30fps).
- A single AI voiceover + SFX audio master that stays in sync across every size.

## Requirements

- **Claude Code** (or a compatible Agent Skills host).
- The **`watch` skill** — the video-watching engine ([`bradautomates/claude-video`](https://github.com/bradautomates/claude-video)):
  ```bash
  # Claude Code:
  /plugin marketplace add bradautomates/claude-video && /plugin install watch@claude-video
  # or any Agent Skills host:
  npx skills add bradautomates/claude-video -g
  ```
- **Node ≥ 18**, **Python 3**, **ffmpeg** + **ffprobe**, **curl** on your PATH (Remotion, audio build).
- Optional: an **OpenRouter API key** (`OPENROUTER_API_KEY`) for the voiceover (`openai/gpt-audio`, voice `coral`). Skip it for an SFX-only or silent film.

## Install

```bash
git clone https://github.com/aariz51/Promo-Video-.git
# make the skill available to Claude Code (global) …
cp -r Promo-Video-/skills/promo-video ~/.claude/skills/promo-video
# … or per-project:
cp -r Promo-Video-/skills/promo-video /path/to/your/project/.claude/skills/promo-video
```

## Use

In Claude Code:

```
/promo-video
```

It will ask for your **reference video URL**, your **app description**, your **assets
folder** (screenshots + logo), which **orientations** you need, and whether you want a
**voiceover** — then it watches, designs, builds, and renders. (You can also just say:
"make me a launch video like <url> for my app — assets are in <folder>".)

## Repo layout

```
skills/promo-video/
├── SKILL.md                         # the workflow the model follows
├── prompt/creative-director-prompt.md   # the exact creative-director brief (parameterized)
├── docs/
│   ├── motion-language.md           # the reusable motion grammar
│   ├── example-breakdown.md         # a fully worked reference breakdown
│   └── appstore-cut.md              # ≤30s / 30fps / exact-size App Preview recipe
└── template/                        # a complete, working Remotion starter
    ├── src/                         # 4 compositions, 9 example scenes, shared components + animations
    ├── scripts/build_audio.py       # streaming OpenRouter VO + meaningful SFX → one master
    └── public/{sfx,fonts}/          # reusable, brand-agnostic assets
```

The `template/` ships as a **working reference implementation** (a warm pregnancy-safety
scanner) so the skill has real, premium code to adapt — not empty stubs. The skill
rewrites the copy, colors, screens, scenes, tagline, logo and audio for *your* app.

## Credits & licenses

- Built on [Remotion](https://remotion.dev) (see Remotion's own license for commercial use).
- Video analysis via [`claude-video` / `watch`](https://github.com/bradautomates/claude-video) (MIT).
- Voiceover via [OpenRouter](https://openrouter.ai) → `openai/gpt-audio`.
- Fonts bundled: Inter & Baloo 2 (SIL Open Font License).
- Bundled SFX are placeholders — verify their licensing before commercial use, or replace them.

MIT © 2026 Aariz Rasheed. See [LICENSE](LICENSE).
