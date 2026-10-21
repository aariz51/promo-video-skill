# QA report — promo-video

Result: **PASS** (0 errors, 0 warnings)

## Checks

- Render produced each requested file, with a video and an audio stream
- Resolution, frame rate and duration match render-config.json
- Full decode pass without errors; no black stretch over 1 s; frozen stretches reported
- Scene timing adds up; no scene under 1.5 s
- Narration: every line rendered, inside its scene, no overlaps
- Audio present; mix contains only library effects, voice and (optional) non-melodic ambience
- Near-silence wherever no cue or line is sounding, so no background music or bed
- Two stills per scene exported for visual review (text overflow, layout)

## Files

- 16:9: `out/promo-16x9.mp4` · 1920×1080 · 30.0 fps · 67.051 s · audio aac · mean -22.8 dB · 18.4 MB

Narration: 6 lines via openrouter

## Issues

- none

## Stills for review

- 16:9: `qa/frames/16x9` (16 frames)
