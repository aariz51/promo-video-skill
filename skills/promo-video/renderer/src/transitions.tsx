import React from "react";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from "remotion";
import { EASE } from "./animations/easings";
import { Bloom } from "./components/Bloom";
import { Whoosh } from "./components/Whoosh";
import type { Direction, Transition } from "./types";

// Each scene's <Sequence> starts at its nominal start and runs `exit.frames` past its
// end, so the next scene's entrance overlaps its tail. The incoming scene draws on top.
//   enter: how this scene arrives (its own transition), over its first frames
//   exit:  how it leaves (the next scene's transition), over its extra tail frames
// `cut` has no frames: the picture changes on one frame, with no blend.
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Where the incoming picture is still hidden, as a clip-path inset, for a wipe whose edge
// travels in `dir` and has covered `p` (0–1) of the frame.
const wipeInset = (dir: Direction, p: number): string => {
  const rest = `${((1 - p) * 100).toFixed(3)}%`;
  switch (dir) {
    case "left":
      return `inset(0 0 0 ${rest})`;
    case "up":
      return `inset(${rest} 0 0 0)`;
    case "down":
      return `inset(0 0 ${rest} 0)`;
    default:
      return `inset(0 ${rest} 0 0)`;
  }
};

const pushOffset = (dir: Direction, p: number): string => {
  const d = (1 - p) * 28;
  switch (dir) {
    case "left":
      return `translate(${d}%, 0)`;
    case "up":
      return `translate(0, ${d}%)`;
    case "down":
      return `translate(0, ${-d}%)`;
    default:
      return `translate(${-d}%, 0)`;
  }
};

export const TransitionFrame: React.FC<{
  enter: Transition;
  exit: Transition;
  duration: number; // nominal frames, excluding the exit tail
  children: React.ReactNode;
}> = ({ enter, exit, duration, children }) => {
  const frame = useCurrentFrame();
  let opacity = 1;
  // A slow, constant camera drift keeps every frame alive between events.
  let scale = interpolate(frame, [0, duration], [1, 1.03]);
  let blur = 0;
  let clip: string | undefined;
  let shift = "";
  let dipVeil = 0; // 0–1 opacity of the dip colour drawn over both pictures

  const curve =
    enter.easing === "linear"
      ? Easing.linear
      : enter.easing === "in"
        ? EASE.in
        : enter.easing === "inOut"
          ? EASE.inOut
          : EASE.out;
  const ei =
    enter.frames > 0
      ? interpolate(frame, [0, enter.frames], [0, 1], {
          ...clamp,
          easing: curve,
        })
      : 1;
  switch (enter.type) {
    case "fade":
      opacity *= ei;
      break;
    case "push":
      opacity *= ei;
      scale *= interpolate(ei, [0, 1], [1.12, 1]);
      blur += (1 - ei) * 14;
      shift = pushOffset(enter.direction ?? "right", ei);
      break;
    case "zoom":
      opacity *= ei;
      scale *= interpolate(ei, [0, 1], [0.86, 1]);
      break;
    case "light":
      opacity *= interpolate(
        frame,
        [enter.frames * 0.45, enter.frames * 0.6],
        [0, 1],
        clamp,
      );
      break;
    case "wipe":
      clip = wipeInset(enter.direction ?? "right", ei);
      break;
    case "dip": {
      // First half: the outgoing picture sinks into the colour (this scene is still
      // invisible, so the one below shows through). Second half: this scene rises out of it.
      const half = enter.frames / 2;
      dipVeil =
        frame < half
          ? interpolate(frame, [0, half], [0, 1], clamp)
          : interpolate(frame, [half, enter.frames], [1, 0], clamp);
      opacity *= frame < half ? 0 : 1;
      break;
    }
    default:
      break;
  }
  if (exit.frames > 0 && frame > duration) {
    const eo = interpolate(frame, [duration, duration + exit.frames], [0, 1], {
      ...clamp,
      easing: EASE.in,
    });
    if (exit.type === "push") {
      scale *= 1 + 0.1 * eo;
      blur += eo * 12;
    } else if (exit.type === "zoom") {
      scale *= 1 + 0.35 * eo;
      opacity *= 1 - eo;
    }
  }
  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          opacity,
          transform: `${shift} scale(${scale})`,
          filter: blur > 0.05 ? `blur(${blur}px)` : undefined,
          clipPath: clip,
        }}
      >
        {children}
      </AbsoluteFill>
      {enter.type === "light" && enter.frames > 0 ? (
        <Bloom
          frame={frame}
          peak={Math.round(enter.frames * 0.5)}
          rise={Math.round(enter.frames * 0.5)}
          fall={Math.round(enter.frames * 0.9)}
        />
      ) : null}
      {enter.type === "dip" && dipVeil > 0 ? (
        <AbsoluteFill
          style={{
            backgroundColor: enter.color === "white" ? "#FFFFFF" : "#000000",
            opacity: dipVeil,
          }}
        />
      ) : null}
      {enter.type === "wipe" && enter.frames > 0 && enter.sweep !== false ? (
        <Whoosh progress={ei} direction={enter.direction ?? "right"} />
      ) : null}
    </AbsoluteFill>
  );
};
