# Voiceover (optional)

**Narration is optional and never required.** Without it, `scripts/build_audio.py`
builds a complete sound-design master — mapped effects, no music — with nothing but
ffmpeg. Many of the best product films have no narration at all.

If you want a voice, the template ships `scripts/voiceover.py`.

## 1. Write the script

`voiceover.json` in the project root — **one short line per scene**, each starting at that
scene's cue (`T` in `src/theme.ts`, converted to seconds):

```json
{
  "voice": "marin",
  "direction": "Bright, warm, confident voice for a premium app advert. Clear, natural pace. Never salesy.",
  "lines": [
    { "at": 0.35, "text": "Every label becomes a question." },
    { "at": 3.10, "text": "With YourApp, one scan is enough." }
  ]
}
```

Writing rules that come from real takes:

- **Keep lines inside their scene.** The tool fits each line to the gap before the next,
  trimming silence and allowing at most a 1.2× tempo change. Past that it flags the line;
  rewrite it rather than pushing the tempo.
- **Don't open a line with a made-up brand name after a full stop.** "BrandName.
  Download free" can come back mangled; "Download BrandName free" reads cleanly. Put
  the name mid-sentence.
- **Lists read slowly.** "Barcode, label, ingredients." took longer than a seven-word
  sentence. For a two-second beat, say one thing.

## 2. Render the lines

```bash
python3 scripts/voiceover.py --engine say          # macOS, keyless, offline
python3 scripts/voiceover.py --engine openrouter   # uses OPENROUTER_API_KEY if you have one
```

- `say` uses a macOS voice name (e.g. `Samantha`). No key, no network.
- `openrouter` uses `openai/gpt-audio`. It reads the key **only** from the
  `OPENROUTER_API_KEY` environment variable, passes it to curl on stdin (never on the
  command line), and never writes it to disk. Female-presenting voices include `marin`,
  `coral` and `shimmer`.

**Every take is verified.** Chat-style TTS models sometimes *answer* a line instead of
reading it — "Scan any label." once came back as "I'm sorry, I can't assist with that
request." The tool frames each line as a script, compares the model's own transcript
with the script, and retries up to four times before telling you to rephrase.

Takes are cached in `scripts/.vo_cache/` (git-ignored), so re-runs are free and
deterministic. Output: `public/audio/vo/NN.wav` and `public/audio/vo/manifest.json`.

## 3. Mix

```bash
python3 scripts/build_audio.py
```

It finds the manifest, places each line at its cue, and side-chain ducks the effects
underneath the voice so speech always reads. No music is added.

## Recording it yourself

Any WAV works. Put it in `public/audio/vo/`, then list it in `manifest.json`:

```json
{ "lines": [ { "file": "00.wav", "at": 0.35 } ] }
```
