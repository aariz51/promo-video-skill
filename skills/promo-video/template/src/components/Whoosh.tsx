import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { COLORS } from "../theme";
import { EASE } from "../animations/easings";

// A saturated brand-gradient blob that smears across the frame with motion-blur
// to change scenes. Drive with local `frame`; sweeps left→right over `span`.
export const Whoosh: React.FC<{
  frame: number;
  start?: number;
  span?: number;
}> = ({ frame, start = 0, span = 26 }) => {
  const { width } = useVideoConfig();
  const p = interpolate(frame, [start, start + span], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.inOut,
  });
  if (p <= 0 || p >= 1) return null;
  const x = interpolate(p, [0, 1], [-width * 0.9, width * 1.1]);
  const op = Math.sin(p * Math.PI); // fade in then out
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: x,
          top: -80,
          width: width * 0.8,
          height: "130%",
          transform: "skewX(-14deg)",
          background: `linear-gradient(90deg, rgba(122,31,162,0) 0%, ${COLORS.purple} 45%, ${COLORS.pink} 70%, rgba(232,75,138,0) 100%)`,
          filter: "blur(40px)",
          opacity: op,
        }}
      />
    </AbsoluteFill>
  );
};
