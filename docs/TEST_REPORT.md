# Test report: v5 production system

Run date: 2026-10-21 · Branch: `feat/production-system` · Machine: macOS (arm64), Python 3.14.7,
Node 26.3.0, ffmpeg 9.0.2, Remotion 4.0.481. This report states what was **executed**; anything
not executed is listed under "Not exercised".

## Suites executed

| Command | Tests | Result | Time |
|---|---|---|---|
| `python3 -m unittest discover -s tests` | 137 (13 skipped: the real-render tests) | OK | ~1 min |
| `PROMO_RENDER=1 python3 -m unittest discover -s tests` | 137, none skipped | **OK** | 3 min 58 s |
| `npx tsc --noEmit` (renderer) | — | exit 0 | — |
| GitHub Actions `ci` (Ubuntu 24.04, ffmpeg 6, Node 20, Python 3.12) | see "CI" below | see below | — |

Per module: `test_pipeline` 50 · `test_modes` 26 · `test_audio_modes` 18 · `test_reference` 18 ·
`test_render` 12 · `test_direction` 9 · `test_deliver` 2 · `test_checklist` 2.

## What the real-render tests did (PROMO_RENDER=1)

Every one drives the real CLI, Remotion and ffmpeg; nothing in this list is mocked.

| Test | Exercised |
|---|---|
| `AutonomousFilm` | Mode A through the CLI: scan → check brief → adapt → creative prompt → check creative → timeline → check timeline → build → QA → deliver. Encoded file: 960×540 draft, 30 fps, frame count = plan, aac, decodes cleanly. Frames: every scene animates and shows content; fade, push, wipe-right and dip-black measured at their planned times; the lockup builds; the dip passes through black; the wipe's edge splits old and new. Two renders of the same film match frame for frame. The delivered project typechecks and lists all five compositions. |
| `AudioModesRendered` | voice-over (macOS `say`; `files` on Linux): aac stream, sfx + voice sources, 3 lines · silent: **no audio stream**, no master, QA PASS (effects-only is `AutonomousFilm`) |
| `ReferenceFilm` | Mode B: synthetic reference → the **installed** `watch` skill (`--no-whisper`) → breakdown → direction → check direction → storyboard → check timeline → build → QA. QA measured the reference's dissolve, wipe-left and dip-black in the film. A blind re-analysis of the film starts every transition inside a reference window. |
| `StoreFormats` | exact 886×1920, 1920×886 and 540×960 (9:16 draft), silent (no stream); the device never touches the frame edge while the camera pushes |
| `EndToEnd` | the v4 end-to-end build still passes |

## Full-resolution verification films

Built with `python3 examples/verification/build.py` (final quality, through the CLI) and
reviewed visually from contact sheets (1–2 frames per second) and full-size stills of suspect
scenes; the defects that review found are fixed (see "Defects found").

| Film | Mode / audio | Files | QA |
|---|---|---|---|
| `examples/verification/autonomous/deliver/videos/promo-16x9.mp4` | A · voice-over (`say`, Samantha, 3 lines) + effects | 1920×1080, 30 fps, 15.5 s, aac, mean −22.3 dB, 3.9 MB | PASS, 0 warnings |
| `examples/verification/autonomous/deliver/videos/promo-store-portrait.mp4` | same | 886×1920, 30 fps, 15.5 s, aac, 3.5 MB | PASS |
| `examples/verification/reference/deliver/videos/promo-16x9.mp4` | B (synthetic "slow" reference) · effects only | 1920×1080, 30 fps, 10.0 s, aac, mean −25.1 dB, 2.5 MB | PASS, 0 warnings |

Transitions measured in the delivered files: Mode A fade→dissolve, push→wipe (accepted family),
wipe right→wipe-right, dip black→dip-black. Mode B reference T01 dissolve→dissolve, T02
wipe-left→wipe-left, T03 dip-black→dip-black. These are generated locally and not committed
(they contain local paths); `build.py` regenerates them.

## Reference analysis, measured on synthetic ground truth

`rapid` (5 scenes, 4 hard cuts, a 120 px/s pan, a fade-out) and `slow` (fade-in, dissolve,
wipe-left, dip to black). Recovered: all cuts to ±1 frame; the dissolve, wipe and dip to
±2 frames, with the wipe's direction; the pan's direction and size (measured −0.60 of the
width vs −0.57 expected); motion inside a scene is not split; opening and closing fades. Our
own renders were also analysed blind, which exposed several analyzer and renderer defects (below).

## Defects found by this testing and fixed

1. Audio mixer failed on ffmpeg ≥ 7 (`-filter_complex_script` removed).
2. Every scene's ground was translucent at its centre, so the previous scene showed through
   during each transition and popped off at its end.
3. The wipe's light sweep ran on its own timing, always left to right.
4. Mode B transitions played half a transition late relative to the reference.
5. In 886×1920 the screen scene's device ran off both edges during its camera push.
6. Mode B films ignored the product's brand colour.
7. The Mode A creative-prompt scaffold ignored the chosen runtime (always ~94 s).
8. Evidence frames past the last video frame (container longer than picture).
9. Analyzer: fixed thresholds missed dark, low-contrast transitions; dips gated wrongly;
   flat-colour alignment ties reported fake camera moves; pans read as wipes; light
   sweeps and incoming entrances broke wipe detection; cache ignored analyzer changes.
10. A `NameError` on the narration-minimum path (no test had covered it).
11. Tests depended on macOS `say` and on the machine's free disk (found by CI and by a full disk).

## Not exercised

- **Live OpenRouter / OpenAI calls.** Provider behaviour (request shape, key on stdin, transcript
  verification, bounded retry, error redaction, model capability check) is tested with the
  network mocked. No paid call was made. Voice-over was rendered for real with macOS `say`.
- **A real YouTube reference.** Mode B was exercised with local synthetic references through the
  installed `watch` skill. URL download paths are tested with a fake `watch.py` and mocks.
- **The `watch` skill's frame extraction.** It fails on ffmpeg ≥ 7 (`-vsync`, upstream). The
  degraded path (watch transcript + promo's own frames) is what ran.
## CI

GitHub Actions run [39638083801](https://github.com/aariz51/promo-video-skill/actions/runs/39638083801)
on commit `3d29db7` (Ubuntu 24.04, ffmpeg 6.1, Python 3.12, Node 20): all three jobs succeeded.

| Job | Result |
|---|---|
| engine tests (no renders) | 137 tests, OK (13 skipped: real renders run in the next job) |
| renderer typecheck | success |
| real renders | 13 tests, OK in 335 s: both modes, voice-over (`files` provider, no `say` on Linux), silent, App Store sizes, delivery, determinism; Mode B ran the "watch skill not installed" path |

The first CI run (`39636085349`, commit `3de7b92`) failed: three audio tests assumed macOS
`say`. Fixed in `3d29db7`.

---

# Follow-up: product-theme discovery and real screenshots (2026-10-22)

Branch `feat/production-system`, starting from `42394b3` (verified on arrival: clean tree, synced,
CI green, 137 tests passing).

## What executed

| Command | Result |
|---|---|
| `python3 -m unittest discover -s tests` (baseline, before changes) | 137 tests OK (13 render tests skipped) |
| `PROMO_RENDER=1 PROMO_MOBILE=1 python3 -m unittest discover -s tests` (final, after the last code change) | 172 tests, **OK**, none skipped, 0 resource warnings (8 min 25 s) |
| `npx tsc --noEmit` (renderer) | exit 0 |
| `python3 examples/verification/build.py` (final code) | three films, QA PASS each (below) |
| GitHub Actions | see CI below |

New tests: `test_discovery.py` (32), `test_render.py` +3 (`test_discovery_drove_the_film`,
`test_the_product_theme_and_real_screens_carry_the_reference_structure`, `RealSimulator`).
None of the 137 earlier tests was removed or weakened. Their fixtures now run the discovery
stage the way the pipeline does, and the fixture timeline no longer forces a dark preset onto
the light fixture product.

## Real product inspection that ran

| Target | What happened |
|---|---|
| Web fixture app (Node server, light/dark tokens, Inter font file) | `npm run dev` launched. `/` and `/reports` render and were captured at 1920×1080 with headless Chrome. `/team` was recorded as HTTP 404 and `/admin` as a login wall, neither captured. `/settings` was held back as possible account data. |
| Broken web fixture (exits, prints a credential) | blocked at "dev server startup"; diagnostic kept with the credential scrubbed (report and `build/launch.log`) |
| Port held by another app | not used, not stopped; blocked with a reason |
| Real Flutter iOS app (`flutter create`, theme, 3 routes) | built with `flutter build ios --simulator` and installed on promo's own simulator (created, then deleted). `/history` and `/result` reached by relaunching with `--route`. Three distinct 1206×2622 captures, inspected visually. |
| Android | no emulator is installed on this machine: reported as `blocked` at device discovery (mocked tests cover the build/launch/capture path) |

## Verification films (final code, generated locally, not committed)

| Film | Discovery | Screens in the film | Theme | Encoded file | QA |
|---|---|---|---|---|---|
| `examples/verification/autonomous/deliver/videos/promo-16x9.mp4` (+ `promo-store-portrait.mp4`, 886×1920) | web app launched and captured | `web-reports` (real `/reports`), callout on its real Export CSV button | light `#F7F5F0`, brand `#1F8A70`, Inter from the product; pixels agree | 1920×1080, 30 fps, 15.5 s, aac, voice-over (`say`) + effects | PASS |
| `examples/verification/reference/deliver/videos/promo-16x9.mp4` | web app launched and captured; synthetic dark reference measured | `web-home` in S02, `web-reports` in S03 | product theme kept over the reference's navy/orange/green fields | 1920×1080, 10.0 s, effects only; dissolve / wipe-left / dip-black measured in the film | PASS |
| `examples/verification/autonomous-mobile/deliver/videos/promo-9x16.mp4` | Flutter app built and captured on the simulator | `ios-result` in a phone frame | light, brand `#1F8A70`; the app declares no font (stated; Inter used) | 1080×1920, 15.5 s, effects only | PASS |

Each `deliver/` holds the video(s), PRODUCT_ANALYSIS.md, THEME_ANALYSIS.md, THEME.json,
ASSET_INVENTORY.md, SCREENSHOT_MANIFEST.json, the selected screenshots, CREATIVE_DIRECTION.md, the
reports and an editable Remotion project carrying the product's font.

## Defects found by running for real, and fixed

1. **False pass on mobile navigation.** `simctl openurl` raised iOS's "Open in …?" prompt; the
   first real run captured the prompt twice and reported both captures as rendered routes. A
   visual check found it. Navigation now uses Flutter's `--route` launch argument and never
   `openurl` on iOS. A warm-up launch and stable-capture rule keep first-boot banners and
   unsettled animations out, and a capture identical to one already taken is recorded as "did
   not navigate".
2. The capture simulator was being created from an iPhone type the runtime doesn't support, and
   that failure was hidden behind the Android message.
3. A commented-out font in `pubspec.yaml` was reported as the product's font.
4. The launch log kept a credential the server printed (now scrubbed).
5. QA's edge check assumed a dark film; it now compares edges with the film's own ground.
6. A wipe whose outgoing scene keeps animating read as "gradual". A wipe is now recognised by
   its revealed side showing the incoming picture.
7. Light UIs looked like near-duplicates of each other (mean brightness); duplicates are now
   judged by structure. 320 px screenshots were being selected; they are now rejected as too small.
8. Primary-colour corroboration sampled too coarsely to see buttons.
9. The ejected Remotion project lacked the product's font; the delivery lacked the new reports
   and screenshots.
10. The manifest's `feature` field was always empty; it now holds the screen's own heading.
11. Unclosed file and HTTP handles.

## Not exercised

- A real Android build and capture: no emulator is installed here (`emulator` is missing; `adb`
  is present with no devices). The path is covered with a mocked toolchain.
- Native iOS (non-Flutter) apps: tested through mocks. Their extra screens cannot be reached
  unattended (custom-scheme links need a person to confirm), and the report says so.
- Authenticated screens: no test credentials exist for the fixture, and none were used.
- The user's own products: none was named for this task, so verification used fixtures.

## CI (follow-up)

All three jobs (engine tests, renderer typecheck, real renders) succeeded on each new commit:
`1edc37d` run 39651890057, `9712526` run 39654110105, `e4b6597` run 39661128031. On Ubuntu the
live web-app discovery tests run for real (Node fixture app + Chrome). The real-simulator test is
macOS-only and opt-in (`PROMO_MOBILE=1`), so CI does not depend on a simulator.
