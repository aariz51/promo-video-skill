# Voiceover and sound

The user chooses the audio once, at the start: **voice-over plus effects**, **effects only**,
or **silent**. It is stored as `audio: {voiceover, soundEffects, music: false}` in
`promo/promo.config.json` and every step obeys it. There is never background music.

| Choice | `promo init --audio` | Voice | Effects | Film's audio |
|---|---|---|---|---|
| A | `voiceover` | yes | yes | voice + effects, effects ducked under speech |
| B | `effects` | never generated | yes | effects only; QA rejects any speech |
| C | `silent` | never generated | none | no audio stream at all (`--muted` render) |

## Writing lines

Narration lives in `timeline.json`, one short line on the scenes that need one. The
framework's rule: explain only what the picture cannot. Many scenes stay silent.

- About 2.7 words per second. `promo compile` rejects a line that cannot fit its scene.
- Say one thing per line. Lists read slowly.
- Put an invented-looking product name mid-sentence rather than first after a full stop;
  TTS engines read "Download Name free" more cleanly than "Name. Download free."
- Numbers in narration need claim ids, like numbers on screen.

## Providers (voice-over mode only)

Chosen with `promo init --provider …`. `promo questions` asks only when it cannot be
inferred: with exactly one API key set, that provider is used; with both set, or none, the
user is asked (and, with none, offered the keyless local voice). A provider that fails is an
error; **the engine never substitutes another one**.

| Provider | Needs | Notes |
|---|---|---|
| `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-audio` (chat completions with audio output; its audio modality is checked against OpenRouter's model list first). Voices `alloy ash ballad coral echo sage shimmer verse marin cedar` |
| `openai` | `OPENAI_API_KEY` | speech endpoint, `gpt-4o-mini-tts`, with delivery instructions; each take is transcribed with `gpt-4o-mini-transcribe` and compared with the script. Voices `alloy ash ballad coral echo fable nova onyx sage shimmer verse` |
| `say` | macOS | offline, keyless; any installed macOS voice name |
| `files` | your recordings | `promo/assets/vo/00.wav`, `01.wav`, … in narration order |
| `auto` | — | the single configured API provider; ambiguity or absence is an error, never a fallback |

`voice.voice` picks the voice; `voice.direction` is one sentence of delivery direction.

Keys are read only from the environment, passed to curl on stdin (never on the command
line), never written to disk, prompts, storyboards or logs, and redacted from every error
message. Never paste a key into chat: export it in your shell.

**Takes are verified.** Chat-style TTS sometimes answers a line instead of reading it. Each
take's transcript is compared with the script and retried up to four times; a line that
never reads cleanly stops the build and asks you to rephrase. Verified takes are cached in
`promo/build/vo-cache/` under a key over provider, model, voice, direction, text, output
format and pipeline version, so an unchanged line is never paid for twice and a changed one
is never reused. A line that overruns its window is sped up at most 1.2×; beyond that the
build stops and asks for a shorter line.

## Sound design

`promo compile` derives cues from scheduled events (see `docs/timeline.md`), and
`promo audio` mixes them with the voice: effects are side-chain ducked under speech,
limited to −1 dBFS. `sound.ambience: true` adds a very low procedural pink-noise bed
(non-melodic by construction); it is off by default.

The effects are synthesised by `engine/promo_engine/sfx_synth.py` from formulas (impacts,
filtered noise, pitch glides; the chime is a single decaying partial set): original to
this project, MIT, and byte-identical on every machine. No third-party sound files ship.

## No background music, no stray audio: how it is guaranteed

1. The config's `audio.music` has one valid value, `false`; anything else is rejected.
2. The effect library contains only short synthesised effects; there is no music file to
   reference, and `timeline.json` cannot name anything outside the library.
3. `promo audio` writes `build/audio-manifest.json` with the policy and every source.
4. `promo qa` fails if the manifest holds an unknown source, an effect longer than 6 s, a
   voice line in effects mode, or anything in silent mode. It then measures the master **and
   each encoded film**: wherever no effect or voice line is sounding, the level must be below
   −45 dBFS, so neither a music bed nor stray speech can pass.
5. Silent films render with `--muted`: QA requires no audio stream, or a stream verified as
   digital silence.
