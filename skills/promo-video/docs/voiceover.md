# Voiceover (optional, not part of the core workflow)

**The skill does not generate narration, and does not need an API key.** Audio is
built locally: `scripts/build_audio.py` mixes the bundled sound effects over a soft
ambient pad using nothing but ffmpeg.

This is a deliberate design decision, not a missing feature.

## Why there is no built-in voiceover

1. **No credential should stand between a user and their first render.** If you have
   Claude Code or Codex, you have everything this skill needs. Adding a TTS provider
   would mean an account, a key, and a billing relationship for one optional track.
2. **Many of the best product films have no voiceover at all.** Plenty of premium SaaS
   launch videos are music and motion only — the type carries the message. If your
   reference has no narration, matching it means not adding any.
3. **Narration is the least portable part of a film.** It locks the edit to one
   language and one read. Sound design does not.

## If you do want narration

The film is a normal Remotion project, so you have the usual options. In rough order
of effort:

**1. Record it yourself.** Thirty seconds of script is a two-minute job on a phone.
Save it as `public/audio/vo.wav`.

**2. Use a TTS tool you already have.** macOS ships `say`:

```bash
say -v Samantha -o public/audio/vo.aiff "Your line here."
ffmpeg -y -i public/audio/vo.aiff -ar 48000 -ac 2 public/audio/vo.wav
```

Linux equivalents include `espeak-ng` and `piper`. These are local and keyless, but
platform-specific — which is exactly why the skill does not depend on one.

**3. Use a hosted TTS provider** if you already have an account somewhere.

## Mixing a voice track in

Once you have `public/audio/vo.wav`, mix it against the SFX master. Time each line to
its scene cue from `T` in `theme.ts`:

```bash
ffmpeg -y -i public/audio/master.wav -i public/audio/vo.wav \
  -filter_complex "[1:a]adelay=300|300,volume=1.25[v];\
                   [0:a]volume=0.55[bed];\
                   [bed][v]amix=inputs=2:normalize=0,alimiter=limit=0.89[out]" \
  -map "[out]" -ar 48000 -ac 2 public/audio/master-vo.wav
```

Then point `AUDIO_SRC` at `"audio/master-vo.wav"`.

Two things worth getting right:

- **Duck the bed under speech.** The `volume=0.55` on the SFX bus above is a static
  duck; a `sidechaincompress` filter does it dynamically if you want to be precise.
- **Fit each line to its window** rather than letting it run over the next scene. A
  pitch-preserving `atempo` between 1.0 and about 1.25 is safe; past that it starts
  to sound rushed.

## One line per scene

Whatever route you take, the writing rule is the same: **one short line per scene**,
timed to that scene's cue. Narration that spans a cut fights the edit. If a line will
not fit its beat, the beat is too short or the line is too long — fix the script, not
the tempo.
