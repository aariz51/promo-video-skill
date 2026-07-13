import { interpolate } from "remotion";
import { EASE } from "./easings";

// Frame-derived motion helpers. All deterministic (no Date/Math.random).

/** Gentle idle bob (sine). amp in px, period in frames. */
export const bob = (frame: number, amp = 10, period = 120, phase = 0) =>
  Math.sin((frame / period) * Math.PI * 2 + phase) * amp;

/** Slow horizontal sway. */
export const sway = (frame: number, amp = 12, period = 150, phase = 0) =>
  Math.cos((frame / period) * Math.PI * 2 + phase) * amp;

/** 0.5→1→0.5 pulse for glows. */
export const pulse = (frame: number, period = 60, phase = 0) =>
  0.5 + 0.5 * Math.sin((frame / period) * Math.PI * 2 + phase);

/** Ease a value across a frame window with a shared curve. */
export const ramp = (
  frame: number,
  from: number,
  to: number,
  a: number,
  b: number,
  easing = EASE.out,
) =>
  interpolate(frame, [a, b], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing,
  });

/** Camera-style push-in scale over a window. */
export const pushIn = (frame: number, a: number, b: number, from = 1, to = 1.08) =>
  ramp(frame, from, to, a, b, EASE.inOut);

/** Fade a scene's tail so cross-scene cuts feel intentional. */
export const tailFade = (
  frame: number,
  sceneDuration: number,
  fadeFrames = 12,
) =>
  interpolate(
    frame,
    [sceneDuration - fadeFrames, sceneDuration],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

/** Deterministic pseudo-random in [0,1) from an integer seed. */
export const seed = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};
