import React from "react";
import { AbsoluteFill, interpolate } from "remotion";

// White radial light-bloom that blows out then recovers — the signature
// section-stitch transition. Drive `frame` relative to the bloom's local start.
export const Bloom: React.FC<{
  frame: number;
  peak?: number; // frame of full white
  rise?: number; // frames to peak
  fall?: number; // frames back to clear
  color?: string;
}> = ({ frame, peak = 8, rise = 8, fall = 14, color = "#FFFFFF" }) => {
  const op = interpolate(
    frame,
    [peak - rise, peak, peak + fall],
    [0, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  if (op <= 0) return null;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 50% 50%, ${color} 0%, ${color} 40%, rgba(255,255,255,0) 75%)`,
        opacity: op,
        pointerEvents: "none",
      }}
    />
  );
};
