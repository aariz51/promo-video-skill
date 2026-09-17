# Scene kit — the parts, and how to recombine them

The template is a **kit plus one worked example**. The nine scenes it ships are what
one particular reference asked for. Your reference will ask for something else.

This file lists what you can reuse, so Step 4 of `SKILL.md` can assemble a structure
instead of inheriting one.

## Components (orientation-agnostic, size-driven)

| Component | What it does | Good for |
|---|---|---|
| `PhoneFrame` | Rounded device with a real screenshot inside, dynamic island, optional glow. Degrades to a labelled placeholder if the image is missing. | any product beat |
| `GlassCard` | Semi-transparent brand-gradient card, soft shadow, inner highlight | callouts, feature chips, floating UI |
| `KineticWords` | Word-by-word spring reveal with per-word keyword colouring | value claims, taglines |
| `Cursor` | Hand cursor that travels and presses real UI | demo/interaction beats |
| `ScoreRing` | Radial gauge that sweeps to a value | proof / reward beats |
| `Confetti` | Physically-simulated, brand-coloured burst | reward beat |
| `Bloom` | White radial bloom that blows out and recovers | act breaks, light↔dark inversions |
| `Whoosh` | Saturated gradient smear with motion blur | scene changes on an audio hit |
| `Particles` | Slow drifting bokeh | ambient depth, never the subject |
| `ActionButton` | Glassy brand orb with a reticle glyph | the primary call-to-action |
| `FontLoader` | Injects the bundled `@font-face` CSS | always mount once, in `Film.tsx` |

## Animation layer

- `springs.ts` — `sEnter` (confident reveal), `sPop` (punchy), `sSettle` (heavy,
  premium), `sBounce` (delight). Everything that enters should use one of these.
- `easings.ts` — `EASE.out` / `.inOut` / `.in` / `.soft`. One curve vocabulary.
- `motion.ts` — `bob`, `sway`, `pulse` (idle life), `ramp`, `pushIn` (camera),
  `tailFade` (scene exits), `seed` (deterministic pseudo-random).

Nothing uses `Math.random()` or `Date`. Renders must be frame-deterministic.

## The nine shipped scenes — and what each is really *for*

Read these as jobs, not as an order. Keep the ones your reference motivates.

| Scene | Job it performs |
|---|---|
| `S1_Hook` | State the problem in one typographic line |
| `S2_OneTap` | The claim: one action solves it |
| `S3_Press` | Interaction proof — cursor presses real UI, dives in |
| `S4_Verdict` | The payoff: result lands, reward fires |
| `S5_MoreThanScan` | Breadth: it is more than the one feature |
| `S6_DeviceOrbit` | Range, in motion — many screens at once |
| `S7_Dashboard` | The money shot, held and annotated |
| `S8_Tagline` | Period-rhythm verbal close |
| `S9_Logo` | Lockup, store badges, exit |

## Writing a new scene

Most references need at least one component that does not exist yet. That is normal.
The contract for a new scene:

```tsx
export const S4_SplitScreen: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;          // portrait stacks, landscape spreads
  const enter = sEnter({ frame, fps });  // shared spring vocabulary
  const opacity = tailFade(frame, dur.split, 14);
  // ...
};
```

Rules that keep a new scene compatible with the rest of the kit:

1. **Read `dur.<yourScene>` from `theme.ts`**, never a hardcoded length.
2. **Branch on `wide`** so all four compositions work from one implementation.
3. **Cap radii and offsets against the frame** so nothing clips at 886 wide or
   886 tall.
4. **Use the shared springs and easings** — a bespoke curve is what makes one scene
   feel bolted on.
5. **No non-determinism.** Use `seed(i)` where you want scatter.

## Common signature devices, and how to build them

These come up often enough across references to be worth naming. None ship as
components; each is a short scene you write from the kit.

- **Typewriter bookend** — a line types in with a caret on one ground, and the closing
  line types in on the *inverted* ground. `interpolate` over character count; blink
  the caret with `pulse`.
- **Split screen** — two `AbsoluteFill` halves with a divider; the user's messy world
  on one side, the product's ordered process on the other, joined by a small connector.
  Stagger the ordered side's rows so it reads as a sequence.
- **System-voice type** — a monospace stack for machine output against the geometric
  sans used for human claims. The contrast alone communicates "this is the software
  talking".
- **Numbered step rows** — an index column plus chip-labelled rows that stagger in.
  Good for explaining a flow without narration.
- **Card scatter** — the same card at several depths with per-card `seed`-driven phase,
  drifting via `bob`/`sway`. Reads as volume and chaos.
- **Light↔dark inversion** — `Bloom` blown to white, with the new ground developing out
  of it. Land it on an audio hit; it is a structural device, not a transition.
