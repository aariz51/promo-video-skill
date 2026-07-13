import { Easing } from "remotion";

// Shared bezier curves — one motion vocabulary across the whole film.
export const EASE = {
  // Smooth, confident settle (default for reveals).
  out: Easing.bezier(0.22, 1, 0.36, 1),
  // Gentle in/out for camera pushes and drifts.
  inOut: Easing.bezier(0.45, 0, 0.55, 1),
  // Snappy anticipation into a hit (whoosh, press).
  in: Easing.bezier(0.5, 0, 0.75, 0),
  // Soft, almost-linear float.
  soft: Easing.bezier(0.4, 0, 0.6, 1),
} as const;
