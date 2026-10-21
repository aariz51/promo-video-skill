# promo-video

**An agent skill that turns your product into a verified promo film.**

Run `/promo-video` in a product's repository. The agent works out what the product does and
which moments are worth showing. Give it a reference video and it measures that video scene
by scene and rebuilds its structure around your product; give it none and it directs the
film itself. It renders with [Remotion](https://remotion.dev), then decodes the film and
measures it against the plan before handing it over.

| You give | You get |
|---|---|
| nothing but the repository | **Mode A, autonomous**: a film directed from the master creative framework |
| a YouTube URL, another video URL, or a local video file | **Mode B, reference-driven**: the reference's scenes, transitions, pacing and camera moves, measured from its pixels and rebuilt around your product |

Formats: 1920×1080, 1080×1920, 1080×1080, and the App Store sizes 886×1920 and 1920×886.
Audio: voice-over plus sound effects, effects only, or silent. Never background music.

---

## Installation

Requirements: Python ≥ 3.11, Node ≥ 18, `ffmpeg`/`ffprobe`. For reference URLs, also
`yt-dlp` and the [`watch`](https://github.com/bradautomates/claude-video) skill.

```bash
git clone https://github.com/aariz51/promo-video-skill.git
cp -r promo-video-skill/skills/promo-video ~/.claude/skills/promo-video      # Claude Code
# or: cp -r promo-video-skill/skills/promo-video ~/.codex/skills/promo-video # Codex

cd ~/.claude/skills/promo-video/renderer && npm ci   # (also runs automatically on first render)

# for reference URLs
brew install yt-dlp                                   # or: pip install yt-dlp
npx skills add bradautomates/claude-video -g          # or in Claude Code: /plugin install watch@claude-video
```

Check the setup: `python3 ~/.claude/skills/promo-video/bin/promo doctor`.

## Usage

```text
/promo-video
/promo-video https://youtu.be/…          # or a local file: /promo-video ~/Movies/reference.mp4
```

The agent asks, once and only if you have not already said:

1. *Do you have a promotional video you want to use as inspiration?* (a URL, a path, or no)
2. *Would you like AI voice-over and professional sound effects? There will be no background
   music.* (A: voice-over + effects · B: effects only · C: completely silent)
3. which voice provider, only if both an OpenRouter and an OpenAI key are configured, or
   neither (then it offers the keyless local voice);
4. which formats, and (without a reference) roughly how long.

Product name, purpose, features, colours and screens come from the repository. Keys are read
from `OPENROUTER_API_KEY` / `OPENAI_API_KEY` in your environment. Never paste one into chat.

## How it works

```
input ─▶ mode + audio policy {voiceover, soundEffects, music: false}
           │
  repository ─▶ scan ─▶ product-brief.md (every claim cites a file)
  reference  ─▶ watch skill + measurement ─▶ reference/breakdown.json, contact sheets
                                          ─▶ CREATIVE_DIRECTION.md (20 fields per scene)
           │
  creative-prompt.md ─▶ timeline.json (Mode B: derived from the breakdown, held to it)
           │
  voice (if chosen) ─▶ synthesised effects (if chosen) ─▶ Remotion render ─▶ QA ─▶ deliver/
```

**Mode B measures, it does not guess.** The engine decodes the reference. It finds every
scene boundary and classifies each transition from the pixels: cut, dissolve, dip to black
or white, wipe and its direction. It estimates each scene's camera move, colour and motion,
and records each transition's speed profile. It saves timestamped evidence frames and
contact sheets. The agent then reads the evidence and fills in what pixels cannot say, such
as what is on screen, typography and narrative function. The storyboard is derived from the
measurements, and `check timeline` holds the film to the reference's order, lengths,
transitions and runtime unless a departure is written down. Two different references give
two structurally different films.

**QA measures the film, not the process.** It decodes each encoded file and checks:

- size, frame rate, duration, and decoding to the last frame;
- black and frozen stretches;
- audio per mode: voice and effects, effects with no speech, or no audio stream at all;
- no music anywhere, by checking every source in the mix and requiring near-silence between cues;
- every scene animates and shows real content;
- every planned transition is present at its planned time;
- in Mode B, every measured reference transition is visible in the film.

Results go to `TEST_REPORT.md` and `qa/validation.json`.

## Workspace

Every step writes an inspectable file to `promo/` in your repository:

```text
promo/
  promo.config.json   product-scan.json   product-brief.md   creative-prompt.md
  reference/          (Mode B) breakdown.json  motion-spec.json  frames/  sheets/
  CREATIVE_DIRECTION.md   timeline.json   storyboard.md   narration.txt   render-config.json
  out/*.mp4           TEST_REPORT.md      qa/validation.json   qa/frames/
  deliver/            films, direction, reports, evidence, and remotion/ (an editable project)
```

## Commands

`promo` = `python3 <skill>/bin/promo`, run from the product's root.

| Command | Does |
|---|---|
| `doctor` | tools, renderer, `watch` skill, voice providers, disk |
| `init` | records the reference (→ mode), audio, provider, formats, runtime, name |
| `questions [--json]` | the opening questions still open |
| `scan` · `capture` | product map · screenshots of the running product |
| `watch [--no-whisper] [--refresh]` | Mode B: run `watch`, measure the reference |
| `direction` · `storyboard` | Mode B: scaffold CREATIVE_DIRECTION.md · reference-derived timeline |
| `adapt` · `check <artifact>` | creative-prompt scaffold · validate brief / direction / creative / timeline |
| `build [--quality draft]` | compile → voice → audio → render → qa |
| `deliver` | assemble the delivery folder |

## Audio

The three choices map to one stored policy that voice, mix, render and QA all obey. Effects
are synthesised by the engine from formulas, so they are original, MIT, and identical on
every machine; no third-party sound files ship. Silent films are rendered with no audio
stream. Voice providers: OpenRouter (`gpt-audio`), OpenAI (`gpt-4o-mini-tts`, each take
transcribed and checked against its line), macOS `say`, or your own recordings. Takes that
do not read their script are retried, then fail loudly. A provider is never swapped silently.
See [`docs/voiceover.md`](skills/promo-video/docs/voiceover.md).

## Originality and accuracy

A reference is a structural and motion input only. No footage, logos, characters, wording
or narration is reused, and a run of seven or more words copied from its transcript fails
validation. Every on-screen or spoken fact traces to a claim that cites a file in your
repository. Numbers need a claim, and invented statistics, reviews or integrations fail.

## Tests

```bash
python3 -m unittest discover -s tests                     # fast suite: ~2 min, no renders
PROMO_RENDER=1 python3 -m unittest discover -s tests      # + real renders of both modes
cd skills/promo-video/renderer && npx tsc --noEmit
```

The reference tests render synthetic clips with known cuts, dissolves, wipes, dips and a
camera pan, and check the analyzer recovers them to the frame. No test downloads a video or
calls a paid API. See [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md) for the latest run and
[`docs/implementation-checklist.md`](docs/implementation-checklist.md) for what is verified.

## Known limits

- Pixel analysis reads a fade into an empty frame like a text reveal, and a push like a camera
  pan; it takes the simpler reading. CREATIVE_DIRECTION.md is where the agent corrects that from
  the frames. QA verifies cuts, fades, wipe directions and dip colours in the film; a push's
  direction is not verified.
- claude-video `watch` 0.2.0 passes `-vsync`, which ffmpeg 7+ removed, so its frame extraction
  fails there. `promo watch` keeps its transcript, measures the frames itself, and records it.

## Credits and licences

- [Remotion](https://remotion.dev): check its licence for commercial use.
- [Cube Motion](https://www.cube-motion.dev) (`cube-motion`, MIT) for UI and type motion.
- [`claude-video` / `watch`](https://github.com/bradautomates/claude-video) (MIT) for video watching.
- Fonts: Inter and JetBrains Mono (SIL Open Font License). Sound effects: synthesised, MIT.
  See [NOTICE](NOTICE).

MIT © 2026 Aariz Rasheed. See [LICENSE](LICENSE).
