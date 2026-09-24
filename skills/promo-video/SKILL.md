---
name: promo-video
description: >-
  Create a premium, cinematic app / SaaS / website promo video in Remotion from a
  product's own screenshots, logo, description and features. Optionally give it a
  REFERENCE video: the skill watches it (via the `watch` skill), reverse-engineers its
  structure, pacing and motion devices, and rebuilds that creative direction around
  your product. Without a reference it uses its own built-in creative system. UI and
  typography motion uses Cube Motion. Mapped sound design; optional voiceover; no API
  key required. Renders 9:16, 16:9 and App Store sizes. Use when the user wants a
  product/app/SaaS launch or promo video, an App Store / Play Store preview video, or
  "a promo like <some video>".
license: MIT
compatibility: >-
  Needs Node >= 18, Python 3 and ffmpeg/ffprobe on PATH. The `watch` skill is needed
  only when a reference video is given. No API key or account is required.
allowed-tools: Bash Read Write Edit AskUserQuestion
user-invocable: true
metadata:
  version: "3.0.0"
  author: aariz51
---

# Promo Video — product launch films, with or without a reference

You are an **Elite Motion Graphics Director + Senior Remotion/React/TypeScript
engineer + Creative Director**. Your work looks premium, cinematic, production-ready.
You think like a creative director before writing a line of code.

## Two modes — chosen by the input, never by the user

| The user gives… | Mode | Structure comes from |
|---|---|---|
| no reference video | **A · autonomous** | the skill's own creative system: the template's nine-scene film and `docs/motion-language.md` |
| a reference video | **B · reference-driven** | the reference: its acts, pacing, transitions and signature devices, rebuilt with the product's assets |

Never ask the user to pick a mode, a library, a provider or a model. If they supplied a
reference, you are in Mode B; otherwise Mode A.

**The rule that defines Mode B:** the reference determines the film's *structure*, not
just its polish. Two different references must produce two structurally different
films for the same product. If you catch yourself reproducing the template's nine
scenes after watching a reference, you have failed the core purpose — see Step 4B.

`SKILL_DIR` = the directory containing this file:
- `prompt/creative-director-prompt.md` — the master brief. **Read it and follow it.**
- `docs/motion-language.md` — reusable motion principles (the vocabulary).
- `docs/scene-kit.md` — the template's components, **Cube Motion** usage, and how to recombine scenes.
- `docs/example-breakdown.md` — a worked reference breakdown, for the depth expected.
- `docs/voiceover.md` — optional narration.
- `docs/appstore-cut.md` — ≤30s / 30fps / exact-size App Preview recipe.
- `template/` — a complete, working Remotion project: the kit, plus the Mode A film.

## Step 0 — Preflight (once)

1. **Tooling.** Confirm `node`, `npx`, `python3`, `ffmpeg`, `ffprobe` are on PATH.
2. **Mode B only — the `watch` skill** (Claude Code plugin `bradautomates/claude-video`,
   or `npx skills add bradautomates/claude-video -g`). If it is missing, tell the user
   how to install it, or ask them for frames instead. Never invent a breakdown.
3. **No API key is required.** Audio is built locally from bundled sound effects.

## Step 1 — Gather inputs (ask, don't guess)

Ask for what the user has not already supplied, in this order. Use `AskUserQuestion`
where it exists and the answer is a real choice; otherwise ask in prose (Codex and other
hosts may not have that tool).

1. **Reference video (optional)** — *"Do you have a promo video whose style you'd like
   me to follow? Paste a URL, or say no."* Any URL yt-dlp supports, or a local path.
2. **Product name** — exactly as it should appear on screen.
3. **Description** — one or two sentences: what it does, and for whom.
4. **Features** — a list, **in priority order**.
5. **Assets** — an absolute path with screenshots and the logo.

If a **codebase** is available, read it first: store listings, README,
`package.json`/`pubspec.yaml` and marketing copy usually hold the real name, description
and feature list. Confirm what you found instead of making the user retype it. Never
invent product facts, statistics or quotes; if you quote the product, quote it verbatim.

Then confirm deliverables (9:16, 16:9, App Store 886×1920 / 1920×886) and duration
(default 33s in Mode A; in Mode B, close to the reference's length).

## Step 2 — Mode B only: watch and reverse-engineer the reference

Use the `watch` skill. Do not rely on one method:

- **Metadata** — length, fps, captions (many premium films have no narration).
- **Scene-cut detection** — the *number* of hard cuts is itself a finding: a film with
  four cuts in 27s is a continuous-camera film.
- **Uniform sampling** — every 0.5–2.5s, 30–60 frames. Tile them into timestamped
  contact sheets and read them in order:
  `ffmpeg -i ref.mp4 -vf "fps=2,scale=512:-1" frames/u_%03d.jpg`
- **Frame-by-frame** (8–12fps) on every signature transition.

If the download fails with **HTTP 403** (YouTube blocks some clients), fetch a
progressive stream with another player client and point `watch` at the local file:

```bash
yt-dlp --extractor-args "youtube:player_client=mweb" -f "18/b[height<=720]" -o ref.mp4 <url>
```

A 360p copy is enough: motion and structure survive, and frames are analysed at 512px.

**Read the frames yourself.** Write the breakdown: acts and their proportions, grounds,
beat rate, every transition, camera moves, typography, colour, composition — and name
the **signature devices** that make it *that* film. You will be held to them in 4B.

## Step 3 — Study the product (inspect, don't assume)

`Read` every screenshot and the logo. Identify the money shot, sample the real brand
colours, and map each feature to the screen that evidences it (a feature with no screen
is a typography beat). Look for real flows you can show honestly — a real query, a real
result, a real label — rather than inventing demo content.

## Step 4 — Structure

### 4A — Mode A: the built-in creative system

Use the template's film: Hook → One-tap promise → Press → Verdict/reward → "More than"
breadth → Device orbit → Money-shot dashboard → Period-rhythm tagline → Logo lockup.
Retarget every scene's copy, screens and palette to the product. Drop a scene only if
the product genuinely has nothing to put in it.

### 4B — Mode B: derive the scene list from the reference

1. Take the reference's **acts and their proportions**; scale them to the target length.
2. Take its **beat rate** and its **cut count**.
3. Give every act a job from the product analysis.
4. For every act, name the reference device you are reproducing, and build it —
   **writing new scene components** for signature devices is expected.
5. **Drop template scenes the reference does not motivate.**

Self-check, answered in the document: *"If I swapped this reference for another, which
scenes would change?"* If the answer is "only copy and colours", start 4B again.

Write the storyboard and production plan. Save everything as `CREATIVE_DIRECTION.md`,
and in Mode B keep the reference evidence (contact sheets) next to it.

## Step 5 — Scaffold

Copy `template/` to the output dir (e.g. `<product>-promo/`), then `npm install`.
Four compositions: `PromoVertical` 1080×1920, `PromoLandscape` 1920×1080,
`PromoStorePortrait` 886×1920, `PromoStoreLandscape` 1920×886.

## Step 6 — Build

- **`src/theme.ts`** — palette, `screens`, `LOGO`, and `T`/`dur` scene boundaries.
- **Assets** — copy into `public/app-screens/` and `public/logo/`.
- **Scenes** — Mode A: retarget the nine. Mode B: write the scenes from 4B.
- **Motion has two layers** (see `docs/scene-kit.md`):
  - *cinematic* — devices, cameras, fly-throughs, charts: `springs.ts`, `easings.ts`,
    `motion.ts`, `interpolate`.
  - *UI and typography* — labels, chips, list rows, captions, badges and any text that
    changes state: **Cube Motion**, via `src/animations/cube.tsx`
    (`CubeRise`, `CubeLeave`, `CubeInOut`, `CubeList`, `CubeMorphText`,
    `CubeMorphSequence`). A status label that changes state is a `CubeMorphText`; a
    list that enters is a `CubeList`. Every `at` is a frame inside the enclosing
    `<Sequence>`. Never import `cube-motion` directly into a scene — its animations are
    time-based and only the bridge makes them frame-accurate.
- **Credibility**: never show a screen that contradicts an overlay; no invented
  statistics; no fabricated quotes; charts without real data carry no axis values.

## Step 7 — Audio (no music by default)

1. Write `sound.json`: one cue per on-screen event, `{ "fx", "at", "vol" }`. Every effect
   must mean something — click on a press, pop on a landing, whoosh on a camera move,
   typing while text writes itself, chime when a result resolves.
2. **Optional voiceover** — only if the user wants narration. Write `voiceover.json`
   (one short line per scene, `at` = that scene's cue) and run
   `python3 scripts/voiceover.py`. Engines: `say` (macOS, keyless) or `openrouter`
   (only if the user already has `OPENROUTER_API_KEY` set). Every take is checked
   against the script and retried if the model answered instead of reading. Fix
   overrunning lines by rewriting them, not by pushing the tempo.
3. `python3 scripts/build_audio.py` — mixes effects (ducked under any voice) with no
   music and no bed. Then set `AUDIO_SRC = "audio/master.wav"`.

## Step 8 — Verify, then render

A successful render is not verification.

- Render stills at every beat, in every orientation you ship, and `Read` them. Fix
  collisions, clipping, overflow, off-brand colour, contradictions.
- Render, then sample the **encoded MP4** (1 frame/second) and read the whole sequence.
- Check the file: `ffprobe` (size, fps, frame count, audio stream), `blackdetect`,
  `freezedetect`, and a decode pass with `ffmpeg -v error -f null -`.
- If there is narration, transcribe the final lines and compare them with the script.

## Step 9 — App Store cut (if requested)

≤30s, 30fps, exact device size. Speed up gently, harder in quiet gaps, output 30fps;
see `docs/appstore-cut.md`. Never letterbox or stretch.

## Host notes

- **Claude Code** — install to `~/.claude/skills/promo-video/`.
- **Codex** — install to `~/.codex/skills/promo-video/`. No `AskUserQuestion`; ask in prose.

Deliver `CREATIVE_DIRECTION.md` and the rendered files, with their exact paths.
