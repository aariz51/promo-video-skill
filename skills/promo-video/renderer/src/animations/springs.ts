import { spring } from "remotion";

// Shared spring presets so every entrance shares one "feel".
// All return a 0→1 progress value.

type SpringArgs = { frame: number; fps: number; delay?: number };

const cfg = {
  // Confident reveal with a hair of overshoot.
  enter: { damping: 16, stiffness: 140, mass: 1 },
  // Punchy pop (buttons, badges, marks).
  pop: { damping: 12, stiffness: 220, mass: 0.8 },
  // Heavy, premium settle (logo, dashboards).
  settle: { damping: 20, stiffness: 110, mass: 1.1 },
  // Bouncy delight (confetti trigger, checkmark).
  bounce: { damping: 9, stiffness: 200, mass: 0.9 },
} as const;

const make =
  (config: (typeof cfg)[keyof typeof cfg]) =>
  ({ frame, fps, delay = 0 }: SpringArgs) =>
    spring({ frame: frame - delay, fps, config });

export const sEnter = make(cfg.enter);
export const sPop = make(cfg.pop);
export const sSettle = make(cfg.settle);
export const sBounce = make(cfg.bounce);
