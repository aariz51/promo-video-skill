# Motion Language — the reusable grammar

These principles are what make the reference family read as *premium*. Preserve them
across any brand; only the palette, type, copy and screens change.

## The engine: word → thing → word → thing
Alternate **kinetic-typography value lines** with **3D product/UI props**. Say the value,
then show the thing that delivers it, then the next value, then the next thing —
escalating to a **proof/reward beat**, a **product reveal**, and a **logo lockup**.
~15–18 discrete beats in ~33s ≈ 1.8s/beat: fast enough to feel modern, breathable enough
to read. Accelerate into the proof beat; exhale on the logo.

## Motion principles
- **Spring, never linear.** Every entrance is a soft spring with a hair of overshoot
  (position + scale + opacity together). Nothing snaps; nothing eases mechanically.
  Presets in `animations/springs.ts` (enter / pop / settle / bounce).
- **Everything floats.** Idle elements have a slow ±6–12px sine bob + micro-parallax, so no
  frame is ever dead-still (`motion.ts` `bob`, `sway`, `pulse`).
- **One focal object per beat.** Strict single-hero composition, optically centered,
  generous negative space. The eye never hunts.
- **3D via CSS perspective, not a real camera.** Panels/phones use `perspective` +
  `rotateX/Y/Z`. "Camera moves" are simulated: push-in = stage `scale`, orbit = ring
  rotation, tilt-reveal = `rotateX → 0`, dive = big `scale` into a bloom.
- **Light-bloom transitions.** A white radial bloom blows to 100% then recovers — hides the
  cut, reads as speed/freshness (`Bloom`).
- **Gradient whoosh wipes.** A saturated brand-color blob smears across with motion-blur to
  change scene, aligned to an audio hit (`Whoosh`).
- **Interaction cue.** A cartoon **hand-cursor travels and presses real UI** — the single
  most "product-demo" device in the film (`Cursor`).
- **Reward physics.** A confetti + check/score beat is the emotional payoff — physically
  simulated, brand-colored (`Confetti`, `ScoreRing`).

## Typography
- Clean geometric grotesque or warm rounded sans (match the brand's personality). Large,
  centered, tight tracking.
- **Keyword-coloring:** paint the *verb/value* word in the brand hue, the rest near-black —
  instant hierarchy without size changes (`KineticWords`).
- **Period-as-rhythm:** "Verb. Verb. Verb." — full stops chunk the line to the beat.
- Word-by-word / letter-cluster reveals with per-word spring stagger (~2–3 frame offsets).

## Color & light
- **Background almost never changes** — a near-white → brand-tint radial with a whisper of
  glow behind the hero. The *props* carry the color.
- **Glassmorphism:** semi-transparent brand-gradient cards, soft ambient shadow, ~20–40px
  radii, faint inner highlight — premium, weightless (`GlassCard`).
- Consistent **z-grammar** the eye learns in the first 3s: background (static) → glass
  props / devices (mid) → headline (front) → cursor (top).

## Sound design (map to on-screen action)
Every effect must *mean* something at that instant: **click** on a cursor tap, **pop** when
something lands/appears, **whoosh** on a camera move/transition, **success chime** + **sparkle**
on the reward/brand beat, **tick-train** while the AI "thinks"/data loads, **card-fan** on a
device orbit. Boost clicks/typing so interactions read. **No music and no ambient bed** by
default; narration, if any, is ducked above the effects. Limit the master to ≈ −1 dB. See
`template/scripts/build_audio.py`.

## Orientation
Author every scene orientation-aware: `const wide = width > height`. Portrait *stacks*
(feature rows, vertical tagline, tall device-orbit, centered device); landscape *spreads*
(card row, horizontal tagline, wide orbit, device-left + copy-right). Keep timing identical
so one audio master syncs all sizes. Cap ring/orbit radii to the frame so nothing clips in
narrow (886-wide) or short (886-tall) App-Store frames.

## Credibility guardrails (a creative director's veto)
- Never let a composited number/label **contradict** the screenshot behind it.
- Avoid alarming **empty-states** (red "0 / getting started") in a reassurance film.
- Don't invent stats. Prefer qualitative, on-message callouts over fake numbers.
- The **money shot** (the core result/value screen) must be clean, believable, and the spine
  of the film.
