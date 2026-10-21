import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { EASE } from "../animations/easings";
import { alpha, useStyle } from "../style";

// An accent-coloured smear that sweeps the frame with motion blur. Drive with a local frame.
export const Whoosh: React.FC<{
  frame: number;
  start?: number;
  span?: number;
}> = ({ frame, start = 0, span = 20 }) => {
  const { width } = useVideoConfig();
  const s = useStyle();
  const p = interpolate(frame, [start, start + span], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.inOut,
  });
  if (p <= 0 || p >= 1) return null;
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: interpolate(p, [0, 1], [-width * 0.9, width * 1.1]),
          top: "-15%",
          width: width * 0.7,
          height: "130%",
          transform: "skewX(-14deg)",
          background: `linear-gradient(90deg, rgba(0,0,0,0) 0%, ${alpha(s.accent, 0.55)} 50%, rgba(0,0,0,0) 100%)`,
          filter: "blur(40px)",
          opacity: Math.sin(p * Math.PI),
        }}
      />
    </AbsoluteFill>
  );
};
