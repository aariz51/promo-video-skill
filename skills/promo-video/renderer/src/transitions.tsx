import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { EASE } from "./animations/easings";
import { Bloom } from "./components/Bloom";
import { Whoosh } from "./components/Whoosh";
import type { TransitionType } from "./types";

// Each scene's <Sequence> starts at its nominal start and runs `exit.frames` past its
// end, so the next scene's entrance overlaps its tail. The incoming scene draws on top.
//   enter: how this scene arrives (its own transition), over its first frames
//   exit:  how it leaves (the next scene's transition), over its extra tail frames
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const TransitionFrame: React.FC<{
  enter: { type: TransitionType; frames: number };
  exit: { type: TransitionType; frames: number };
  duration: number; // nominal frames, excluding the exit tail
  children: React.ReactNode;
}> = ({ enter, exit, duration, children }) => {
  const frame = useCurrentFrame();
  let opacity = 1;
  // A slow, constant camera drift keeps every frame alive between events.
  let scale = interpolate(frame, [0, duration], [1, 1.03]);
  let blur = 0;
  let clip: string | undefined;

  const ei =
    enter.frames > 0
      ? interpolate(frame, [0, enter.frames], [0, 1], {
          ...clamp,
          easing: EASE.out,
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
      clip = `inset(0 ${(1 - ei) * 100}% 0 0)`;
      break;
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
          transform: `scale(${scale})`,
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
      {enter.type === "wipe" && enter.frames > 0 ? (
        <Whoosh frame={frame} start={-4} span={enter.frames + 8} />
      ) : null}
    </AbsoluteFill>
  );
};
