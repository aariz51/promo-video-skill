import React from "react";
import { interpolate } from "remotion";
import { COLORS, FONT_HEAD } from "../theme";
import { EASE } from "../animations/easings";

// A signature score gauge: an arc that sweeps to a value with the
// number counting up. Drive with local `frame`; sweep over [start, start+span].
export const ScoreRing: React.FC<{
  frame: number;
  score?: number; // 0-100 target
  size?: number;
  stroke?: number;
  color?: string;
  trackColor?: string;
  start?: number;
  span?: number;
  label?: string;
}> = ({
  frame,
  score = 92,
  size = 300,
  stroke = 22,
  color = COLORS.safe,
  trackColor = "rgba(47,181,106,0.16)",
  start = 0,
  span = 45,
  label,
}) => {
  const p = interpolate(frame, [start, start + span], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const value = Math.round(p * score);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const filled = (value / 100) * c;
  const glowP = interpolate(p, [0.85, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={trackColor} strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${c}`}
          style={{ filter: `drop-shadow(0 0 ${8 + glowP * 16}px ${color})` }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: FONT_HEAD,
        }}
      >
        <div style={{ fontSize: size * 0.34, fontWeight: 800, color: COLORS.ink, lineHeight: 1 }}>
          {value}
        </div>
        <div style={{ fontSize: size * 0.11, fontWeight: 600, color: COLORS.inkSoft, marginTop: -2 }}>
          /100
        </div>
        {label ? (
          <div style={{ fontSize: size * 0.1, fontWeight: 700, color, marginTop: 6, opacity: glowP }}>
            {label}
          </div>
        ) : null}
      </div>
    </div>
  );
};
