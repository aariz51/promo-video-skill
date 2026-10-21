---
name: promo-video
description: >-
  Make a cinematic launch/promo film for the product in the current repository. The skill
  inspects the codebase, optionally watches a YouTube video for creative inspiration (via
  the claude-video `watch` skill), turns both into a product-specific creative prompt, and
  renders an original 1920×1080 film with Remotion: real product moments, sparse
  voiceover, mapped sound design, no background music, automated QA. Works for any app,
  SaaS, website, mobile app, AI product, developer tool or startup. Use when the user
  asks for a promo video, launch film, product video, demo video, or "a promo like <URL>".
license: MIT
compatibility: >-
  Needs Python >= 3.11, Node >= 18, ffmpeg/ffprobe. The `watch` skill
  (bradautomates/claude-video) and yt-dlp are needed only for the inspiration path.
allowed-tools: Bash Read Write Edit AskUserQuestion
user-invocable: true
argument-hint: "[YouTube inspiration URL]"
metadata:
  version: "4.0.0"
  author: aariz51
---

# /promo-video

You are the creative director and the production team. Two inputs go in: **the product**
(this repository) and, optionally, **an inspiration video**. One original film comes out.

```
PRODUCT REPOSITORY ──scan──▶ PRODUCT PROMO BRIEF ─────────────────────┐
                                                                      ├─▶ PRODUCT-SPECIFIC ─▶ timeline ─▶ voice + sound ─▶ render ─▶ QA ─▶ film
YOUTUBE URL ──watch──▶ YOUTUBE INSPIRATIONAL PROMPT ──┐               │    PROMO PROMPT
        (or, with no URL: MASTER CREATIVE FRAMEWORK) ─┴───────────────┘
```

`SKILL_DIR` is the folder holding this file. Run every engine step as
`python3 "$SKILL_DIR/bin/promo" <command>` from the product's root (the workspace is
`./promo/`). Everything the pipeline decides is written to a file there, so it can be
inspected and edited.

| File in `promo/` | Written by | Contract |
|---|---|---|
| `product-scan.json` | `promo scan` | what the repo evidences, with paths |
| `product-brief.md` | you | `framework/product-brief.template.md` · `promo check brief` |
| `inspiration/evidence.json`, `pacing.json` | `promo watch` | frames, transcript, cut timings |
| `inspiration-analysis.md` | you | `framework/inspiration-analysis.template.md` · `promo check inspiration` |
| `creative-prompt.md` | `promo adapt` + you | `framework/creative-prompt.template.md` · `promo check creative` |
| `timeline.json` | you | `docs/timeline.md` · `promo check timeline` |
| `storyboard.md`, `narration.txt`, `render-config.json` | `promo compile` | derived, never hand-edited |
| `out/promo-16x9.mp4` | `promo render` | the film |
| `qa-report.md`, `qa/frames/` | `promo qa` | must PASS, and you must look at every still |

## Step 1 — Open like a creative director (one question)

Infer everything you can. Ask only this, with `AskUserQuestion` (or in prose on hosts
without it). Mention that you will use the current repository as the product.

> I'll make the promo for the product in this repository.
> **Do you have a YouTube video you want to use as visual inspiration?**
> - **Yes — I have an inspiration video** (then ask: "Send me the YouTube URL.")
> - **No — create the creative direction yourself**

If the user already gave a URL with the command, skip the question. If the product is not
the current directory, ask where it is. Do not ask for name, description, features,
colours or assets: those come from the repository. Ask later only for what the repo truly
cannot tell you (for example, credentials needed to launch it).

Then:

```bash
python3 "$SKILL_DIR/bin/promo" doctor
python3 "$SKILL_DIR/bin/promo" init --product . --inspiration "<URL or none>"
```

`init` validates the URL. On a bad URL, show the reason and ask again; never guess a URL.

## Step 2 — Understand the product (Layer 2)

```bash
python3 "$SKILL_DIR/bin/promo" scan
```

The scan is a map, not an answer. Go deeper than the README: read the source files it
points to (routes, screens, components, commands, services, tests, docs, design tokens)
until you can answer: what it does, for whom, what makes it valuable, which workflows are
visually compelling, which moment is the "wow", which screens deserve hero treatment.

**See the real product.** If it can run, run it: `promo capture --launch --routes / /x`
starts its dev command, waits for it, and screenshots each route into `promo/assets/captures/`
(or start it yourself and pass `--url`). Read every capture. For a CLI or agent tool, run
its real commands and keep their real output. Existing screenshots, logos and recordings
in the repo can be copied into `promo/assets/`. If the product cannot launch, say why and
use only real material that exists; never draw UI the product does not have.

Write `promo/product-brief.md` from the template: PRODUCT, TARGET USER, CORE PROBLEM,
VALUE PROPOSITION, HERO FEATURES, PRODUCT MOMENTS, VISUAL ASSETS, DEMO OPPORTUNITIES,
FACTUAL CLAIMS (`- C1: … — source: path:line`), RESTRICTIONS. Every claim cites a file
that says it. When unsure, leave the claim out. Run `promo check brief` until it passes.

## Step 3 — Path A only: watch the inspiration (Layers 3–4)

```bash
python3 "$SKILL_DIR/bin/promo" watch "<URL>"
```

This runs the installed `watch` skill (claude-video): download, scene-aware frames,
transcript; then measures every hard cut into `pacing.json`. If `watch` is missing,
`promo doctor` prints the install command; if the video cannot be analysed, **stop and
tell the user**: offer another URL or the no-inspiration path. Never write an analysis
of a video you did not watch.

**Read every frame listed in `inspiration/evidence.json`**, in order, in parallel Read
calls. For fast sections, re-run `watch` on the downloaded file with `--start/--end` for
denser frames. Then write `promo/inspiration-analysis.md` as the
**YOUTUBE INSPIRATIONAL PROMPT**, with the template's twelve sections exactly: identity,
hook (first 1–5 s, and why it works structurally), timestamped story structure, pacing
(use `pacing.json`'s numbers), motion language, visual language, sound language,
narration structure, typography system, transition system, cinematic arc, and 10–20
reusable creative rules, each with the timestamp that evidences it.

Describe *how* it is made, never *what it says*: no copied narration, wording, logos,
graphics or shots. `promo check inspiration` rejects copied transcript phrases, missing
timestamps, and timestamps past the video's end.

**Path B (no inspiration):** skip this step. The **MASTER CREATIVE FRAMEWORK**
(`framework/master-creative-framework.md`) is the creative source. Read it in full.

## Step 4 — Transform: the PRODUCT-SPECIFIC PROMO PROMPT (Layer 5)

```bash
python3 "$SKILL_DIR/bin/promo" adapt
```

`adapt` does the mechanical half: it carries the source's rules into CREATIVE DNA,
rescales the source's scenes and pacing to the target runtime (60–100 s by default), and
lays out one SCENE PLAN row per source beat. You do the creative half: replace every
TODO so that structure, pacing, motion, typography, transitions, sound and narration
style come from the source, while subject, visuals, UI, features, claims and words come
only from the brief. Delete framework beats the product cannot support truthfully; merge
or split inspiration beats when the product's story needs it, and say so in ORIGINALITY.

Rules that hold here:
- **Show, don't tell.** Every capability is input → process → result using real material.
- A strong hook before the name; one hero demonstration; a still, confident ending.
- Sparse narration: about one short line per beat, many beats silent; no fluff.
- **No background music**: voice, effects, silence and non-melodic ambience only.
- Every on-screen or spoken fact maps to a claim id in FACT CHECK.

`promo check creative` must pass. Show the user a short summary: core message, the arc,
and what was taken from the inspiration (or framework) versus the product.

## Step 5 — Author the timeline (Layer 6)

Write `promo/timeline.json` from the creative prompt. It is an ordered list of scenes; each
uses one primitive, documented with every prop in `docs/timeline.md`:

`hook` · `wordzoom` · `title` · `statement` · `pillars` · `screen` · `flow` · `terminal` · `document` ·
`montage` · `compare` · `metric` · `lockup`

Each scene has an `id`, `kind`, `duration` (s), `purpose`, `props`, optional
`transition` (`fade` `light` `push` `zoom` `wipe` `cut`), optional `narration`, `claims`
(ids) and `source` (the rule or beat it realises). Media paths are relative to
`promo/assets/`. Use real captures and real text: real commands and output in `terminal`,
real sections in `document`, real steps in `flow`. Numbers need claim ids. Put the
product's accent colour in `style.accent`.

```bash
python3 "$SKILL_DIR/bin/promo" check timeline
python3 "$SKILL_DIR/bin/promo" compile      # → render-config.json, storyboard.md, narration.txt
```

Compilation schedules every event (fragment freeze, step arrival, typed line, callout)
and derives the sound cues from the same times, so picture and sound share one clock.

## Step 6 — Produce, render, verify (Layers 7–8)

```bash
python3 "$SKILL_DIR/bin/promo" build        # compile → voice → audio → render → qa
```

Or step by step: `voice`, `audio`, `render [--quality draft]`, `qa`. Render a **draft**
first, look at it, fix, then render final.

- **Voice:** `voice.provider` `auto` uses OpenRouter's gpt-audio if `OPENROUTER_API_KEY`
  is set, else macOS `say`; `files` uses your own recordings. Every take is checked against
  the script. A line that overruns its scene stops the build: shorten the line.
- **Audio:** effects mapped to events, ducked under the voice. No music, ever.
- **QA** checks resolution, frame rate, duration, streams, decode errors, black and frozen
  stretches, narration placement, and proves there is no music (only library effects, voice,
  and silence between them). It exports one still per scene to `promo/qa/frames/`.

**A passing QA report is not the end.** Read every still in `qa/frames/`. Fix text
overflow, collisions, empty-looking frames, off-brand colour, anything that looks like a
slideshow, and any frame that contradicts the brief. Re-compile and re-render until both
QA and your own review pass. Check free disk space before long renders.

For 9:16 and 1:1: `promo render --aspect 9:16 --aspect 1:1` (same timeline, adapted layout).

## Step 7 — Present

Tell the user, briefly: what you understood about the product; (Path A) the creative
patterns you extracted; how they were adapted; the scene list; what QA checked; and the
exact output paths. Show artifacts and decisions, not private reasoning.

## Failure rules

Stop and explain, never paper over: invalid or inaccessible URL, `watch` failure, no
transcript (say so in the analysis), missing tools (show `promo doctor`), product will not
launch, missing assets, TTS failure, malformed timeline, render failure (the log path is
printed), unsupported media. Never continue on invented information.

## Reference

- `framework/master-creative-framework.md` — the default creative framework (Path B).
- `framework/*.template.md` — the three artifact contracts.
- `docs/timeline.md` — every primitive and prop. `docs/architecture.md` — the layers.
- `docs/motion-language.md`, `docs/voiceover.md`, `docs/aspect-ratios.md`.
