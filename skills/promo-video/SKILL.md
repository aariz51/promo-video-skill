---
name: promo-video
description: >-
  Make a professional promo film for the product in the current repository (or a product
  you point at). With no reference video it directs the film itself; with a reference video
  (YouTube, another video URL, or a local file) it measures that video's scenes, transitions
  and motion and rebuilds that structure around the product. Renders with Remotion in
  1920×1080, 1080×1920, 1080×1080 and the App Store sizes 886×1920 / 1920×886. Voice-over plus
  sound effects, effects only, or silent: never background music. Every film is decoded
  and measured against its plan before delivery. Use when the user asks for a promo video, launch film,
  product video, App Store preview, or "a promo like <URL>".
license: MIT
compatibility: >-
  Needs Python >= 3.11, Node >= 18, ffmpeg/ffprobe. The `watch` skill (bradautomates/claude-video)
  and yt-dlp are used for reference URLs.
allowed-tools: Bash Read Write Edit AskUserQuestion
user-invocable: true
argument-hint: "[reference video URL or path]"
metadata:
  version: "5.0.0"
  author: aariz51
---

# /promo-video

You are the creative director and the production team. Two inputs go in: **the product**
and, optionally, **a reference video**. One verified film comes out.

The mode follows from the input, never from a question about modes:

| Input | Mode | Creative structure comes from |
|---|---|---|
| no reference | **A: autonomous** | the MASTER CREATIVE FRAMEWORK (`framework/master-creative-framework.md`) |
| YouTube / other video URL / local video file | **B: reference-driven** | the reference, measured scene by scene (`reference/breakdown.json`) |

`SKILL_DIR` is the folder holding this file. Run every step as
`python3 "$SKILL_DIR/bin/promo" <command>` from the product's root; the workspace is
`./promo/`. Every decision is a file there, so each stage can be inspected and re-run.

## Step 1: Open (one batch of questions, asked once)

Record whatever the user already said with `init`, then ask only what is still open:

```bash
python3 "$SKILL_DIR/bin/promo" doctor
python3 "$SKILL_DIR/bin/promo" init --product . [--reference <url|path|none>] [--audio voiceover|effects|silent] \
    [--provider openrouter|openai|say|files] [--formats 16:9 9:16 1:1 store-portrait store-landscape] \
    [--runtime 30-45] [--name "…"]
python3 "$SKILL_DIR/bin/promo" scan
python3 "$SKILL_DIR/bin/promo" questions --json
```

`questions` lists only undecided items, in this order, and never one already answered or
evidenced by the repository. Ask them together with `AskUserQuestion` (prose on hosts
without it), then record the answers with `init`:

1. **reference** — "Do you have a promotional video you want to use as inspiration? Paste
   its URL or local file path, or say no."
2. **audio** — "Would you like AI voice-over and professional sound effects? There will be
   no background music. If you want AI voice-over, do you already have an OpenRouter or
   OpenAI API key configured in the environment?"
   - A. Voice-over plus professional sound effects (`--audio voiceover`)
   - B. Professional sound effects only, no narration (`--audio effects`)
   - C. Completely silent: no voice-over, effects or music (`--audio silent`)
3. **provider** — only when voice-over was chosen and it cannot be inferred: both keys set,
   or none (then say what is missing and offer the keyless local voice, `say`, if present).
   Never ask for a key in chat; keys come from `OPENROUTER_API_KEY` / `OPENAI_API_KEY`.
4. **product / assets** — only when the scan cannot tell (no name or purpose; no screenshots).
5. **formats**, and **runtime** (Mode A only; Mode B keeps the reference's length).

The audio choice is stored as `{voiceover, soundEffects, music: false}`. `music` has no
other valid value. `init` rejects a reference it cannot resolve (bad URL, missing or
undecodable file); show the reason and ask again. Never guess a URL.

## Step 2: Discover the real product (PRODUCT_THEME_DISCOVERY, both modes)

```bash
python3 "$SKILL_DIR/bin/promo" discover            # codebase, theme, live app, real screenshots
python3 "$SKILL_DIR/bin/promo" select [--approve id …] [--reject id … --reason "…"]   # optional review
```

`discover` refuses to treat this skill's own repository as the product. It then:

- reads the codebase;
- launches the web app with its own safe `dev`/`start` script, or reuses an instance already
  serving this product (never one serving something else);
- checks each route, recording 404s, login walls, runtime-error overlays, blank pages and
  broken assets instead of capturing them;
- captures the routes that render into `promo/assets/captured/web/`.

For a mobile project it detects the stack and uses its own iOS Simulator (never someone
else's booted one) or a running Android emulator or device. It then builds and launches the
app, follows the app's own deep links, and captures into `assets/captured/mobile/`.
Screenshots already in the repository, or passed with `--supplied`, are registered as
*supplied*. Files in `assets/illustrations/` are *illustrations*, never real screens. Use
`--url` for an authorised test instance, `--no-launch` when launching is not possible (it is
then recorded as not inspected), and never submit payments, messages or deletions to get a
screen.

It writes:

- `PRODUCT_ANALYSIS.md`
- `THEME_ANALYSIS.md`
- `THEME.json`, the product's palette per mode, fonts and interface language with evidence,
  and the film's use of it
- `ASSET_INVENTORY.md`
- `SCREENSHOT_MANIFEST.json`, every candidate with its source, size, state, limitations and
  a selected-or-not reason

**Open and look at every selected screenshot.** If something it needed was blocked (credentials,
a broken build, no simulator), say so to the user and carry on with what is genuine. Never
replace the product with placeholder UI.

The scan and analysis are a map, not an answer. Read the source they point to until you can
say what the product does, for whom, and its strongest visual demonstration (the "money shot").

Write `promo/product-brief.md` (`framework/product-brief.template.md`). Every claim is
`- C1: … — source: path:line`; when unsure, leave it out. No invented statistics, users,
reviews, prices, integrations or awards. `promo check brief` must pass.

## Step 3B: Mode B only — measure and direct from the reference

```bash
python3 "$SKILL_DIR/bin/promo" watch [--no-whisper]     # watch skill + promo's own measurement
python3 "$SKILL_DIR/bin/promo" direction                # scaffolds CREATIVE_DIRECTION.md
```

Run this after `discover`: the direction document maps the reference's scenes onto the
product's real screens and theme. `watch` runs the installed `watch` skill (transcript, frames) and then measures the file
itself: metadata, every scene boundary, each transition's type (cut, dissolve, dip to
black/white, wipe and its direction, or `gradual` when none fits), each scene's camera move,
colour and motion, evidence frames and timestamped contact sheets in `promo/reference/`. If
the `watch` skill is missing or its frame extraction fails, promo measures the file itself
and the evidence says so. If the video cannot be fetched or decoded, **stop and tell the
user**: offer another reference or Mode A. Never write a breakdown of a video you did not
measure.

**Read every contact sheet and evidence frame** listed in `reference/breakdown.json`, then
replace every TODO in `CREATIVE_DIRECTION.md`. For each of the 20 fields per scene, write what
is visible first and mark interpretation as `Interpretation:`. Describe how the reference
is made, never what it says: no copied narration, logos, footage or distinctive assets.
Fill the transition table, the motion language, 10–20 reusable rules (each citing S##/T## or
a timestamp) and the adaptation decisions. Fill PRODUCT THEME (what is kept from the product,
what is adapted for the film and why) and the SCREENSHOT MAPPING (which real screen carries
each reference scene, the feature it proves, how it is cropped). The reference controls
structure and motion; the product controls content, interface and branding.
`promo check direction` must pass.

## Step 4: Creative prompt

```bash
python3 "$SKILL_DIR/bin/promo" adapt
```

`adapt` scaffolds `promo/creative-prompt.md`. Mode A: the framework's arc, scaled to the
runtime. Mode B: the measured scenes and the direction's rules. Replace every TODO from the brief: structure, pacing, motion and sound
from the source; subject, visuals, claims and words from the product. One hero demonstration;
sparse narration; no background music. `promo check creative` must pass.

## Step 5: Timeline

Mode A: write `promo/timeline.json` from the creative prompt (`docs/timeline.md`).
Mode B: start from the reference's structure:

```bash
python3 "$SKILL_DIR/bin/promo" storyboard     # one scene per measured scene, measured transitions
```

Fill `kind`, `purpose`, `props` (and `narration`) for each scene from the brief, using the
storyboard's `suggest` (a real screen proposed for that reference scene) where it fits. Keep
`ref`, `duration` and `transition`. A departure needs a `deviation` reason on the scene, or a
`reference.dropped` entry with a reason. `promo check timeline` enforces the reference's
order, lengths, transitions and runtime in Mode B, and real assets and sourced numbers in both.

**The product's look comes from `THEME.json`.** The film's ground, ink, accent and type are
the product's own. A light product makes a light film, and a reference's palette never
replaces the brand. A departure needs `style.deviation` with a reason. Show product UI only
as `shot:<id>` from the manifest (approved, genuine). An illustration needs
`"illustrative": true` on the scene and must never pass for a real screen.

Primitives: `hook` `wordzoom` `title` `statement` `pillars` `screen` `flow` `terminal`
`document` `montage` `compare` `metric` `lockup`. Transitions: `cut` `fade` `push` `wipe`
`zoom` `light` `dip` (with `direction`, `color`, `easing`, `sweep` where they apply).

## Step 6: Build and verify

```bash
python3 "$SKILL_DIR/bin/promo" build --quality draft   # compile → voice → audio → render → qa
python3 "$SKILL_DIR/bin/promo" build                   # final quality, every requested format
```

- **Voice** runs only in voice-over mode, with the chosen provider; a provider is never
  swapped silently. Each take is checked against its script line and retried a bounded
  number of times. Takes are cached by every input that changes them.
- **Audio**: effects are synthesised by the engine, timed to on-screen events. Effects-only
  mode never generates speech. Silent mode builds no mix, and the film has no audio stream.
- **QA** (`TEST_REPORT.md`, `qa/validation.json`) checks the encoded files. That covers size,
  frame rate, duration, decode, black and frozen stretches, and audio per mode, with no music
  and no speech between cues. It also checks that every scene animates and shows content,
  that every planned transition is present at its time, and in Mode B that each reference
  transition is visible in the film.

**A passing report is not the end.** Look at the stills in `qa/frames/` and fix text
overflow, collisions, empty-looking frames, off-brand colour, anything that reads as a
slideshow, and anything that contradicts the brief. Re-build until QA and your own review
pass. `promo doctor` reports free disk; renders need about 1–2 GB.

## Step 7: Deliver

```bash
python3 "$SKILL_DIR/bin/promo" deliver
```

`promo/deliver/` holds the films, the discovery reports and selected screenshots,
`CREATIVE_DIRECTION.md`, storyboard, brief, the reports,
the reference evidence (Mode B), and `remotion/`, an editable Remotion project with this
film as its default. Tell the user briefly: the mode and why, what was taken from the
reference or framework versus the product, the scene list, what QA verified, and the
exact paths.

## Failure rules

Stop and explain, never paper over: product root is this skill, app will not launch (say
which stage failed and what that means for the film), no simulator or emulator, unresolvable reference, inaccessible or undecodable
video, missing tools (`promo doctor`), product will not launch, missing assets, provider not
configured or failing, a voice take that will not match its script, malformed timeline,
render failure (the log path is printed), QA failure, low disk. Never continue on invented
information.

## Reference

- `framework/master-creative-framework.md` (Mode A), `framework/*.template.md` (artifact contracts)
- `docs/timeline.md` (every primitive, prop and transition) · `docs/architecture.md`
- `docs/motion-language.md` · `docs/voiceover.md` · `docs/aspect-ratios.md`
