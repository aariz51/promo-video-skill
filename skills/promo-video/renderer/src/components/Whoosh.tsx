import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { alpha, useStyle } from "../style";
import type { Direction } from "../types";

// An accent-coloured smear riding a wipe's edge, with motion blur. It takes the wipe's own
// eased progress and direction, so the light and the reveal move as one edge.
export const Whoosh: React.FC<{
  progress: number; // 0–1, the share of the frame the wipe has covered
  direction: Direction; // the way the edge travels
}> = ({ progress: p, direction }) => {
  const { width, height } = useVideoConfig();
  const s = useStyle();
  if (p <= 0 || p >= 1) return null;
  const vertical = direction === "up" || direction === "down";
  const span = vertical ? height : width;
  const band = span * 0.35;
  // Edge position along the travel axis, measured from the side the wipe starts on.
  const edge = direction === "left" || direction === "up" ? (1 - p) * span : p * span;
  const gradient = `linear-gradient(${vertical ? "180deg" : "90deg"}, rgba(0,0,0,0) 0%, ${alpha(
    s.accent,
    0.55,
  )} 50%, rgba(0,0,0,0) 100%)`;
  return (
    <AbsoluteFill style={{ pointerEvents: "none", overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          left: vertical ? "-10%" : edge - band / 2,
          top: vertical ? edge - band / 2 : "-15%",
          width: vertical ? "120%" : band,
          height: vertical ? band : "130%",
          transform: vertical ? "skewY(-6deg)" : "skewX(-14deg)",
          background: gradient,
          filter: "blur(40px)",
          opacity: Math.sin(p * Math.PI),
        }}
      />
    </AbsoluteFill>
  );
};
