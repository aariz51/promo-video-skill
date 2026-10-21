import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { seed } from "../animations/motion";
import { alpha, useStyle } from "../style";

// Slow, seeded dust drifting upward. Depth, never the subject.
export const Particles: React.FC<{
  count?: number;
  opacity?: number;
  salt?: number;
}> = ({ count = 26, opacity = 1, salt = 0 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const s = useStyle();
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {new Array(count).fill(0).map((_, i) => {
        const r = seed(i + salt * 101);
        const r2 = seed(i + 97 + salt * 101);
        const size = 2 + r * 5;
        const x = r2 * width + Math.sin(frame / (90 + r * 60) + i) * 18;
        const y =
          ((((1 - r) * height - frame * (0.12 + r2 * 0.3)) % height) + height) %
          height;
        const tw = 0.15 + 0.25 * (0.5 + 0.5 * Math.sin(frame / 40 + i));
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              width: size,
              height: size,
              borderRadius: "50%",
              background: i % 4 === 0 ? s.accent : s.ink,
              opacity: tw * opacity * (s.dark ? 0.6 : 0.35),
              boxShadow: `0 0 ${size * 3}px ${alpha(i % 4 === 0 ? s.accent : s.ink, 0.5)}`,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
