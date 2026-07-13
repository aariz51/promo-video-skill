# Worked example — reference breakdown (depth to aim for)

A model of the analysis Step 2 must produce. This one reverse-engineers a real SaaS
launch ad (LangEase by *Zelios*, 33.1s, 1280×720, light theme, ~music-synced, no VO) —
the reference the template's example film was built from. Match this specificity for
whatever video the user provides.

## Macro-structure — 8 movements
The film alternates *kinetic-typography value lines* and *3D product/UI props*, escalating
to a proof beat, a product reveal, and a logo lockup. **word → thing → word → thing.**

| # | t (s) | Movement | On screen |
|---|-------|----------|-----------|
| 1 | 0.0–3.0 | Kinetic hook | "Turn Books" builds word-by-word, centered, on light lavender. Keyword in blue, rest near-black. |
| 2 | 3.0–5.0 | Floating glass prop | value line flanks a frosted-glass blue **folder card**; a cartoon hand-cursor drifts in. |
| 3 | 5.0–7.0 | Perspective UI + bloom | a dashboard panel tilts flat in 3D; a white bloom flashes over the cut. |
| 4 | 7.0–9.5 | Device orbit hero | value line centered while **iPhone mockups orbit in a 3D ring**; blurred pages drift behind. |
| 5 | 10–11 | Whoosh wipe | a phone swipes off-left as a **blue gradient whoosh** wipes the frame (motion-blur). |
| 6 | 12–14 | Proof beats | "**94/100**" with a glossy **progress bar** filling L→R → "**Done**" + frosted **checkmark** + **confetti**. |
| 7 | 15–26 | Product showcase | content cards slide → full dashboard in perspective with an animated **hand-cursor clicking** → one card multiplies into a grid → a floating button is **pressed** → branded dashboard slides in. |
| 8 | 27–33 | Tagline + logo | "**Translate. Dub. Distribute**" (each word its own hue) + a small star that **forms** center → resolves into the **wordmark + mark**. |

## Motion principles (the *how*)
Spring-everything (est. damping ~14–18, medium stiffness); everything floats (slow sine bob +
micro-parallax); one focal object per beat; 3D via CSS `perspective` + `rotateX/Y/Z` (no real
camera — push-in = `scale`, orbit = ring rotation, tilt-reveal = `rotateX→0`); white light-bloom
stitches (used ~5s and ~24s); saturated gradient whoosh wipe at ~10s aligned to a hit; a custom
hand-cursor that travels and presses real UI; a confetti + checkmark reward at ~13s; a
count-up "94/100" + progress bar as the "proof" grammar.

## Typography
Geometric grotesque (Inter / SF Pro family), regular–medium, tight tracking, large, centered.
Keyword-coloring paints the value word in the brand hue, rest near-black. Period-as-rhythm.
Word-by-word reveals with per-word spring stagger.

## Color & light
Background near-white lavender `#F3F4F9 → #EEF0F7` with a whisper of radial glow; the *props*
carry the color (blue `#2E7DF7 / #3B82F6`, indigo `#4F46E5`, sky `#7CB8FF`, pink confetti
`#F472B6`). Glassmorphism: semi-transparent brand-gradient cards, soft shadow, ~20–24px radii,
faint inner highlight. Text near-black `#0E1116`.

## Why it works
It never shows a feature without first *saying the value* (word → thing). It earns the product
reveal with abstraction first, proves it with a real dashboard + a real click, rewards with
confetti, then brands. Classic Apple/Stripe launch grammar compressed to 33s: ~1.8s/beat,
accelerating into the proof beat, exhaling on the logo.

---

**Then translate, don't transplant.** The template's example film keeps this exact grammar but
swaps the cold blue minimalism for a warm cream/purple/pink/gold world, a scan-button + safety
score-ring hero, a "SAFE" reward, and a heart logo — same design family, completely original.
Do the same for the user's app and reference.
