// The contract between the engine and the renderer. `render-config.json`, written by
// `promo compile`, is passed in as the composition's input props. Every time in `_t` is in
// seconds, relative to the scene's start, and was scheduled by the engine: scenes read
// their event times from here instead of inventing their own, so sound and picture share
// one clock.

export type TransitionType =
  | "none"
  | "cut"
  | "fade"
  | "light"
  | "push"
  | "wipe"
  | "zoom"
  | "dip";

export type Direction = "left" | "right" | "up" | "down";

// How a scene arrives. `direction` (wipe, push) is the way the edge or picture travels;
// `color` (dip) is what the picture passes through.
export type Transition = {
  type: TransitionType;
  frames: number;
  direction?: Direction;
  color?: "black" | "white";
};

export type Style = {
  preset: "graphite" | "paper" | "midnight";
  ground: string;
  ground2: string;
  ink: string;
  inkSoft: string;
  accent: string;
  line: string;
  dark: boolean;
  fontHead: string;
};

export type Scene = {
  id: string;
  kind: SceneKind;
  purpose: string;
  from: number;
  durationInFrames: number;
  transition: Transition;
  // Props differ per kind; each scene component narrows them.
  props: Record<string, unknown> & { _t: Record<string, unknown> };
  claims: string[];
};

export type SceneKind =
  | "hook"
  | "wordzoom"
  | "title"
  | "statement"
  | "pillars"
  | "screen"
  | "flow"
  | "terminal"
  | "document"
  | "montage"
  | "compare"
  | "metric"
  | "lockup";

export type RenderConfig = {
  version: 1;
  product: string;
  source: "framework" | "inspiration";
  seed: number;
  fps: number;
  durationInFrames: number;
  duration: number;
  style: Style;
  scenes: Scene[];
  audio: { src: string | null };
};
