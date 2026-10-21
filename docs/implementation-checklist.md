# Implementation checklist

Machine-readable: one row per requirement, pipe-separated, columns fixed. `tests/test_checklist.py`
parses this table and fails if a `PASS` row has no evidence. Statuses: `NOT_STARTED`,
`IN_PROGRESS`, `BLOCKED`, `PASS`, `FAIL`.

Audit: [engineering-audit.md](engineering-audit.md). Run evidence: [TEST_REPORT.md](TEST_REPORT.md).

| ID | Requirement | File / subsystem | Evidence | Status | Blocker |
|---|---|---|---|---|---|
| BASE-1 | Audio mixer works on ffmpeg 6–9 (no `-filter_complex_script`) | engine/audio.py | `AudioMix.test_mix_is_effects_and_voice_only` passes on ffmpeg 9.0.2 | PASS | |
| CFG-1 | One canonical run config `audio {voiceover, soundEffects, music:false}`; music can never be enabled; invalid config rejected | engine/config.py | | NOT_STARTED | |
| CFG-2 | Mode chosen from input: none → A; YouTube / other video URL / local video file → B; bad input is an error, never a guess | engine/reference_input.py, cli init | | NOT_STARTED | |
| CFG-3 | Opening questions computed from what is known; nothing already supplied is asked again | engine/questions.py, cli `questions` | | NOT_STARTED | |
| CFG-4 | Voice provider resolved explicitly and recorded; ambiguity is asked; no silent substitution | engine/config.py, voiceover.py | | NOT_STARTED | |
| AUD-1 | Voice-over + effects mode: narration and effects, never music | voiceover.py, audio.py, qa.py | | NOT_STARTED | |
| AUD-2 | Effects-only mode: no speech generated, mix has no voice | voiceover.py, audio.py, qa.py | | NOT_STARTED | |
| AUD-3 | Silent mode: no voice, no effects, no mix, exported file has no audio stream | render.py, qa.py | | NOT_STARTED | |
| AUD-4 | Effects are licence-clean (procedurally synthesised, deterministic, short) | engine/sfx_synth.py | | NOT_STARTED | |
| AUD-5 | OpenAI TTS provider with transcript verification; OpenRouter path preserved | voiceover.py | | NOT_STARTED | |
| AUD-6 | Voice cache key covers provider, model, voice, direction, text, format, pipeline version | voiceover.py | | NOT_STARTED | |
| AUD-7 | API keys never written to workspace files or printed | voiceover.py, tests | | NOT_STARTED | |
| REF-1 | Reference metadata from the real file: duration, fps, size, aspect, audio, captions | engine/reference.py | | NOT_STARTED | |
| REF-2 | Scene boundaries and transition types (cut / dissolve / dip) measured from pixels | engine/reference.py | | NOT_STARTED | |
| REF-3 | Evidence frames per scene and transition, timestamped contact sheets | engine/reference.py | | NOT_STARTED | |
| REF-4 | Machine-readable breakdown + motion spec with full-duration coverage | engine/reference.py | | NOT_STARTED | |
| REF-5 | Missing watch, inaccessible URL, failed download, malformed and truncated files fail loudly | watcher.py, reference.py | | NOT_STARTED | |
| REF-6 | Analysis cached by input fingerprint | engine/reference.py | | NOT_STARTED | |
| DIR-1 | CREATIVE_DIRECTION.md (Mode B): 20 fields per scene, transitions, motion spec, decisions; validated | engine/direction.py | | NOT_STARTED | |
| DIR-2 | Reference-derived storyboard skeleton (scene count, durations, transitions from the breakdown) | engine/direction.py, cli `storyboard` | | NOT_STARTED | |
| DIR-3 | Mode B timeline is checked against the reference structure; deviations must be declared | engine/timeline.py | | NOT_STARTED | |
| DIR-4 | Two different reference fixtures produce materially different storyboards | tests | | NOT_STARTED | |
| DIR-5 | Mode A writes CREATIVE_DIRECTION.md from the creative prompt and storyboard | engine/direction.py | | NOT_STARTED | |
| RND-1 | Renderer implements measured transitions (`cut` hard, `dip` to black/white) | renderer/src/transitions.tsx | | NOT_STARTED | |
| RND-2 | Exact App Store compositions 886×1920 and 1920×886 alongside 1920×1080, 1080×1920 | renderer/src/Root.tsx, config.py | | NOT_STARTED | |
| RND-3 | Draft renders keep even dimensions for every format | config.py, render.py | | NOT_STARTED | |
| RND-4 | TypeScript compiles; compositions load | renderer | | NOT_STARTED | |
| ANI-1 | Frame-level animation checks on a real render (scene start/mid/end, transitions, lockup) | tests/test_render.py | | NOT_STARTED | |
| E2E-A | Autonomous integration: fixtures → brief → direction → storyboard → render → validation | tests/test_render.py | | NOT_STARTED | |
| E2E-B | Reference integration: synthetic reference → frames → breakdown → storyboard → render → validation | tests/test_render.py | | NOT_STARTED | |
| E2E-AUD | All three audio modes rendered and inspected with ffprobe | tests/test_render.py | | NOT_STARTED | |
| QA-1 | QA writes `qa/validation.json` and `TEST_REPORT.md`, mode-aware | qa.py | | NOT_STARTED | |
| DEL-1 | `promo deliver` assembles videos, direction, storyboard, reports, editable Remotion project | engine/deliver.py | | NOT_STARTED | |
| CI-1 | GitHub Actions runs unit tests, typecheck and a smoke render | .github/workflows/ci.yml | | NOT_STARTED | |
| DOC-1 | SKILL.md and docs describe the implemented behaviour | SKILL.md, docs/ | | NOT_STARTED | |
| GIT-1 | Milestones committed and pushed; remote commits verified | git | | NOT_STARTED | |
