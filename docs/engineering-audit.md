# Engineering audit: promo-video-skill

Date: 2026-10-21 · Branch audited: working tree on `main` (last commit `124414a`) · Auditor: repository-first trace of the code, not the docs.

## 0. What is actually in the repository

There are two versions of the skill, and the difference matters for everything below.

| | Where | Shape |
|---|---|---|
| **v3** | GitHub `main` (`124414a`) | `skills/promo-video/template/`: a Remotion project with nine hand-written scenes (`S1_Hook` … `S9_Logo`), `scripts/build_audio.py`, `scripts/voiceover.py`, `prompt/creative-director-prompt.md`, `docs/scene-kit.md`, `docs/appstore-cut.md`. The agent copies the template into the product and edits scene code. |
| **v4** | Uncommitted in the working tree (never pushed) | A "creative compiler": a Python engine (`engine/promo_engine/`, CLI `bin/promo`) that writes and validates intermediate artifacts, plus one data-driven Remotion renderer (`renderer/`) with 13 parameterised scene primitives. v3's `build_audio.py` / `voiceover.py` were moved into the engine (`audio.py`, `voiceover.py`). 48 unit tests in `tests/`. |

**Decision.** Build on v4. It is the more complete implementation, it already has tests, and discarding it would throw away working, unpushed work. The v3 features that v4 dropped and that this task requires (App Store 886-wide formats, a nine-beat autonomous structure) are ported forward, not resurrected as the old template. The first commit on `feat/production-system` therefore contains the v4 tree as found plus a compatibility fix, so the history shows what was inherited and what changed after.

## 1. Current architecture (v4)

```
/promo-video (SKILL.md: agent instructions)
  └─ bin/promo → promo_engine.cli
       init     config.py      promo/promo.config.json (product root, inspiration URL, voice, aspects)
       scan     analyzer.py    product-scan.json (manifests, README, routes, assets, colours, launch plan)
       capture  capture.py     headless-Chrome screenshots of the running product
       watch    watcher.py     runs claude-video watch.py → inspiration/evidence.json + pacing.json (ffmpeg cut detection)
       check    artifacts.py   validates product-brief.md, inspiration-analysis.md, creative-prompt.md
       adapt    adapter.py     scaffolds creative-prompt.md (framework beats or inspiration rows, rescaled)
       compile  timeline.py    timeline.json → render-config.json (+ per-scene event times `_t`), storyboard.md, narration.txt; sound.py derives cues
       voice    voiceover.py   OpenRouter gpt-audio or macOS `say` or user files; verified, cached
       audio    audio.py       ffmpeg mix of effects + voice → build/public/audio/master.wav + audio-manifest.json
       render   render.py      `npx remotion render` per aspect, staged public dir
       qa       qa.py          ffprobe/ffmpeg checks, no-music proof, stills → qa-report.md, qa/qa.json
```

Renderer: `renderer/src/Root.tsx` registers `Promo16x9` (1920×1080), `Promo9x16` (1080×1920), `Promo1x1` (1080×1080). `Film.tsx` lays scenes on the clock from `render-config.json`; `transitions.tsx` implements `fade light push zoom wipe cut`; `layout.ts` sizes in `u` (1% of the short side) and branches on aspect. Cube Motion is bridged through `animations/cube.tsx` and seeked to the Remotion frame.

## 2. Actual end-to-end execution path

1. Agent reads `SKILL.md`, asks one question ("Do you have a YouTube video…?").
2. `promo doctor`, `promo init --inspiration <url|none>`; `init` only accepts YouTube URLs (`youtube.parse_youtube_url`).
3. `promo scan` → agent reads source → writes `product-brief.md` → `promo check brief` (claims must cite existing files).
4. Path A only: `promo watch <url>` → `watch.py` subprocess → parse markdown report → `detect_cuts` (ffmpeg scene score ≥ 0.3) → `pacing.json`. Agent Reads frames and writes `inspiration-analysis.md` (12 sections) → `promo check inspiration`.
5. `promo adapt` → `creative-prompt.md` scaffold → agent fills → `promo check creative`.
6. Agent writes `timeline.json` → `promo check timeline` → `promo compile`.
7. `promo build` = compile → voice → audio → render → qa.

Traced and confirmed by running the unit suite (section 5) and reading each module.

## 3. Capabilities that already work

- Product scan with evidence paths; secret-named files and `.env` are never read (tested).
- Claim discipline: brief claims must cite files that exist; numbers on screen need claim ids (tested).
- `watch` integration: locates the installed skill in the standard layouts, runs it, parses its report, falls back to a mweb download on YouTube 403, and stops (no invented analysis) on failure (tested with a fake `watch.py`).
- Hard-cut detection and pacing statistics from the real file (tested on a synthetic clip).
- Copy guard: 7-word runs from the reference transcript fail the checks (tested).
- Timeline schema validation, deterministic event scheduling, sound cues derived from the same times (tested).
- Voice-over: OpenRouter gpt-audio with the key passed on curl's stdin, take verification against the script (handles the "model answers instead of reading" failure), cache, fitting lines to scene windows (`say` path exercised in earlier example builds).
- QA: resolution, fps, duration, decode errors, black and frozen stretches, narration placement, no-music proof (allowed sources only, short effects only, near-silence between cues) (tested on synthetic files).
- Three aspect ratios share one timeline and one audio master.
- TypeScript compiles (`tsc --noEmit` exit 0 after `npm ci`).

## 4. Missing or incomplete functionality (against the task)

| # | Gap | Evidence |
|---|---|---|
| G1 | **Audio mixer is broken on current ffmpeg.** `audio.py` uses `-filter_complex_script`, removed in ffmpeg 7+. Every `promo audio` / `promo build` fails here. | `test_mix_is_effects_and_voice_only` errors: `Unrecognized option 'filter_complex_script'` (ffmpeg 9.0.2) |
| G2 | **No audio-preference model.** There is no voice-over + effects / effects-only / silent choice. Effects are always mixed; narration is on by default; QA *requires* an audio stream, so a silent film cannot pass. No `music:false` in the run config. | `config.py` DEFAULTS, `qa.check_video` ("no audio stream" is an error) |
| G3 | **Reference input is YouTube-only at init.** Local files and other yt-dlp URLs are rejected by `init`, although `watcher.watch` accepts a local path. | `cli.cmd_init` → `parse_youtube_url` |
| G4 | **Reference analysis is not evidence-structured.** Only hard cuts are measured. No metadata stage (fps, aspect, audio presence), no per-scene evidence frames, no contact sheets, no transition classification (dissolve, dip to black), no motion measurement, no machine-readable scene/transition breakdown. The scene table is free text written by the agent and only checked for timestamps. | `watcher.py`, `artifacts.check_inspiration` |
| G5 | **Reference does not provably drive the build.** The adapter scaffolds a prompt from the agent's prose rows; nothing checks that the timeline's scene count, durations or transitions follow the reference. Two references could produce the same film unnoticed. | `adapter.py`, `timeline.validate` |
| G6 | **No `CREATIVE_DIRECTION.md`** with the per-scene 20-field breakdown, transition analysis, motion spec and decision record. | — |
| G7 | **Transition vocabulary cannot express a measured dip-to-black or a hard cut with motion handoff**; `cut` exists but `fade` is the default when unspecified. | `transitions.tsx`, `TRANSITIONS` |
| G8 | **App Store formats were dropped.** v3 rendered 886×1920 and 1920×886; v4 has only 16:9, 9:16, 1:1. | `config.ASPECTS`, `Root.tsx`, deleted `docs/appstore-cut.md` |
| G9 | **OpenAI provider missing.** Only OpenRouter, `say`, files. `OPENAI_API_KEY` is ignored. | `voiceover.py` |
| G10 | **Silent provider substitution.** `auto` quietly falls back from OpenRouter to `say`, which the task forbids. The resolved engine is not recorded before generation. | `voiceover.pick_engine` |
| G11 | **Voice cache key** uses the OpenRouter model for every engine and omits the output format and pipeline version. | `voiceover.take` |
| G12 | **Bundled sound effects have unverified licensing.** `NOTICE` says their provenance "has not been verified for commercial redistribution". | `NOTICE` |
| G13 | **No visual/animation tests.** No test renders frames and checks that motion happens; the only render test is an opt-in end-to-end. | `tests/test_pipeline.py` |
| G14 | **No mode-selection / question-planning logic in code.** Whether a question must be asked is only in SKILL.md prose; nothing records answers or prevents re-asking. | — |
| G15 | **No CI.** `.github/` holds issue templates only. | `.github/` |
| G16 | **Deliverables** (`TEST_REPORT.md`, machine-readable validation report, editable project) are not produced as such: QA writes `qa-report.md` and `qa/qa.json`; the renderer is shared and not exported. | `qa.py` |
| G17 | **Draft renders of odd-sized formats.** At draft scale 0.5, 886 wide → 443 px, which H.264 yuv420p cannot encode. | `QUALITY["draft"]` |

## 5. Failure cases and weak points

- ffmpeg major-version drift (G1) silently disabled the whole audio path; nothing in `doctor` checks ffmpeg capabilities.
- `watch` fallback download only runs for YouTube; another-site failure goes straight to an error (correct, but the message is YouTube-specific).
- `check_no_music` skips the silence proof when ambience is on, and does not prove that an effects-only mix contains no speech.
- `qa.check_video` treats "no audio stream" as an error unconditionally, contradicting a silent mode.
- `render.stage` copies files by mtime; a deleted asset leaves stale files in `build/public` (harmless: the timeline is validated first).
- `voiceover.render_voice` deletes previous takes in `build/public/audio/vo` before checking the provider, so a failing provider leaves the workspace without voice files (cache survives).
- `analyzer` colour extraction counts colours in source text; it does not read logo pixels.

## 6. Required changes (mapped to gaps)

1. Pass the mixer's filter graph inline (portable across ffmpeg 6–9) (G1).
2. `audio` block in the run config: `{voiceover, soundEffects, music:false, provider}`; validated on every load; music can never be true; `init --audio voiceover|effects|silent` persists it; voice, audio, render and QA obey it; silent renders use Remotion `--muted` so the file has no audio stream; QA checks per mode (G2, G10).
3. Reference resolver: none → Mode A; YouTube or other http(s) video URL → Mode B; existing local video file → Mode B; anything else → error. Mode is derived, never asked (G3, G14).
4. `reference.py`: ffprobe metadata; per-frame scene-score signal; cut / dissolve / dip-to-black classification; per-scene motion energy, brightness and dominant colour; scene evidence frames (start/mid/end) and transition frames; timestamped contact sheets; cached by input fingerprint; `reference/breakdown.json` + `motion-spec.json` (G4).
5. `CREATIVE_DIRECTION.md` scaffolded from the breakdown with the 20 fields per scene, a transition table, the motion spec and a decision record; `check direction` rejects missing fields, missing evidence files, invalid scene ids, TODOs (G6). Mode A gets a generated `CREATIVE_DIRECTION.md` from the creative prompt and storyboard.
6. `promo storyboard` derives a timeline skeleton from the breakdown (scene count, scaled durations, mapped transitions); `check timeline` in Mode B verifies each scene's `ref` and that structure stays within tolerance of the reference, with explicit `deviation` notes required otherwise (G5).
7. Renderer: add `dip` transition (to black or white) and honour `cut` with no blend; App Store compositions 886×1920 and 1920×886 (G7, G8).
8. OpenAI TTS provider with transcription-based verification; explicit provider resolution recorded in config; no silent fallback; cache key over every generation input (G9–G11).
9. Replace unverified effects with deterministic procedurally synthesised effects generated by the engine (original work, MIT) (G12).
10. Frame-level animation tests on a real low-resolution render; audio-mode render tests; reference tests on synthetic clips; CI workflow (G13, G15).
11. QA writes `qa/validation.json` and `TEST_REPORT.md`; `promo deliver` assembles deliverables including an editable Remotion project (G16).
12. Draft scale per format chosen so both sides stay even (G17).

## 7. Test coverage gaps (before this work)

| Area | Before |
|---|---|
| Audio modes (voice+fx / fx / silent) | none |
| Silent export has no audio stream | none |
| Mode selection from input | YouTube URL parsing only |
| Reference metadata, frames, contact sheets, transitions | hard cuts only |
| Breakdown ⇄ storyboard consistency; two references differ | none |
| Animation actually moves between frames | none |
| Real render in default test run | none (opt-in E2E only) |
| OpenAI provider, provider substitution, secret leakage into files | none |
| TypeScript compile in tests / CI | none |

## 8. Backward-compatibility risks

- `inspiration-analysis.md` (v4 Path A) is superseded by `CREATIVE_DIRECTION.md`. Existing v4 workspaces keep working for Mode A; Mode B workspaces must re-run `promo watch` + `promo reference`. `examples/self-promo-inspired` is kept as a historical example and marked as v4-format.
- `config.voice.provider` remains accepted; the new `audio` block takes precedence and is filled from it when absent (`provider:none` → effects only).
- `qa-report.md` is renamed `TEST_REPORT.md`; `qa/qa.json` is kept and `qa/validation.json` added.
- Replacing the effect files changes how existing example films would sound on re-render.
- New aspect keys (`store-portrait`, `store-landscape`) are additive.

## 9. Prioritised implementation checklist

Tracked with status and evidence in [`implementation-checklist.md`](implementation-checklist.md). Order:

1. Baseline + ffmpeg fix (unblocks every audio test).
2. Run configuration: modes, audio preferences, provider resolution, question planning.
3. Audio modes end to end (voice, mixer, silent render, QA per mode) + synthesised effects.
4. Reference analysis engine + synthetic fixtures.
5. CREATIVE_DIRECTION.md + reference-derived storyboard + structure checks.
6. Renderer: dip transition, App Store formats, even draft sizes.
7. Animation/frame tests and render integration tests for both modes.
8. Deliverables, docs, CI.
9. Final regression, report, push.

## 10. Outcome (2026-10-21)

Every gap G1–G17 is closed, each with test evidence: see
[`implementation-checklist.md`](implementation-checklist.md) (every row PASS, with evidence) and
[`TEST_REPORT.md`](TEST_REPORT.md) (what was executed, the full-resolution films, CI, and what
was not exercised). Testing exposed further defects beyond this audit (translucent ground,
late Mode B transitions, portrait cropping, analyzer weaknesses on dark footage, and an
ffmpeg incompatibility in the upstream `watch` skill). They are fixed or worked around, and
listed in the test report.
