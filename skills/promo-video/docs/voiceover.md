# Voiceover and sound

Every film has sparse voiceover by default, and never background music.

## Writing lines

Narration lives in `timeline.json`, one short line on the scenes that need one. The
framework's rule: explain only what the picture cannot. Many scenes stay silent.

- About 2.7 words per second. `promo compile` rejects a line that cannot fit its scene.
- Say one thing per line. Lists read slowly.
- Put an invented-looking product name mid-sentence rather than first after a full stop;
  TTS engines read "Download Name free" more cleanly than "Name. Download free."
- Numbers in narration need claim ids, like numbers on screen.

## Providers

Set `voice.provider` in `promo/promo.config.json` (or `promo voice --provider …`).

| Provider | Needs | Notes |
|---|---|---|
| `auto` (default) | — | `openrouter` if `OPENROUTER_API_KEY` is set, else `say` on macOS, else a clear error |
| `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-audio`; voices `alloy ash ballad coral echo sage shimmer verse marin cedar` |
| `say` | macOS | offline, keyless; any installed macOS voice name |
| `files` | your recordings | `promo/assets/vo/00.wav`, `01.wav`, … in narration order |
| `none` | `narration.enabled: false` + reason | only when narration would damage the concept |

`voice.voice` picks the voice; `voice.direction` is one sentence of delivery direction.

The OpenRouter key is read only from the environment, passed to curl on stdin (never on
the command line), and never written to disk or logs.

**Takes are verified.** Chat-style TTS sometimes answers a line instead of reading it. Each
take's transcript is compared with the script and retried up to four times; a line that
never reads cleanly stops the build and asks you to rephrase. Takes are cached in
`promo/build/vo-cache/`. A line that overruns its window is sped up at most 1.2×; beyond
that the build stops and asks for a shorter line.

## Sound design

`promo compile` derives cues from scheduled events (see `docs/timeline.md`), and
`promo audio` mixes them with the voice: effects are side-chain ducked under speech,
limited to −1 dBFS. `sound.ambience: true` adds a very low procedural pink-noise bed
(non-melodic by construction); it is off by default.

## No background music: how it is guaranteed

1. The effect library contains only short effects; there is no music file to reference.
2. `timeline.json` cannot name anything outside that library.
3. `promo audio` writes `build/audio-manifest.json` listing every source in the mix.
4. `promo qa` fails if the manifest contains an unknown source or any effect longer than
   6 s, and it measures the master: wherever no effect or voice line is sounding, the
   level must be below −45 dBFS. A music bed cannot pass that.
