import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";
import { COLORS } from "../theme";
import { seed } from "../animations/motion";

// Deterministic confetti burst — the reward beat. Drive with local `frame`;
// pieces launch upward/outward from center then fall, fading out.
export const Confetti: React.FC<{
  frame: number;
  start?: number;
  count?: number;
  life?: number;
}> = ({ frame, start = 0, count = 80, life = 130 }) => {
  const { width, height } = useVideoConfig();
  const t = frame - start;
  if (t < 0 || t > life + 20) return null;

  const palette = [COLORS.pink, COLORS.purple, COLORS.gold, COLORS.pinkSoft, COLORS.purpleSoft, COLORS.goldSoft];
  const cx = width / 2;
  const cy = height * 0.46;

  const pieces = new Array(count).fill(0).map((_, i) => {
    const a = seed(i) * Math.PI * 2;
    const spd = 9 + seed(i + 7) * 20;
    const vx = Math.cos(a) * spd * (0.6 + seed(i + 3));
    const vy = -Math.abs(Math.sin(a)) * spd - 6 - seed(i + 11) * 8;
    const g = 0.34;
    const x = cx + vx * t;
    const y = cy + vy * t + 0.5 * g * t * t;
    const rot = t * (4 + seed(i + 5) * 8) * (seed(i + 2) > 0.5 ? 1 : -1);
    const life2 = Math.min(1, t / life);
    const op = 1 - Math.max(0, (life2 - 0.6) / 0.4);
    const w = 10 + seed(i + 4) * 14;
    const h = 6 + seed(i + 6) * 10;
    const col = palette[i % palette.length];
    return { x, y, rot, op, w, h, col, round: seed(i + 8) > 0.6 };
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {pieces.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: p.x,
            top: p.y,
            width: p.w,
            height: p.round ? p.w : p.h,
            background: p.col,
            borderRadius: p.round ? "50%" : 2,
            opacity: p.op,
            transform: `rotate(${p.rot}deg)`,
          }}
        />
      ))}
    </AbsoluteFill>
  );
};
