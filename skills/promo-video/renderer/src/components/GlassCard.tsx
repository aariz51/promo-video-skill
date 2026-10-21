import React from "react";
import { alpha, useStyle } from "../style";

// Glass panel with a hairline border and a faint top highlight. Used for product UI,
// callouts and cards. `active` lights the border in the accent colour.
export const GlassCard: React.FC<{
  width?: number | string;
  height?: number | string;
  radius?: number;
  active?: number; // 0..1
  fill?: number; // accent fill amount 0..1
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({
  width,
  height,
  radius = 24,
  active = 0,
  fill = 0,
  children,
  style,
}) => {
  const s = useStyle();
  const base = s.dark ? "rgba(255,255,255,0.045)" : "rgba(255,255,255,0.72)";
  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        position: "relative",
        background:
          fill > 0
            ? `linear-gradient(160deg, ${alpha(s.accent, 0.22 * fill)}, ${base})`
            : base,
        border: `1.5px solid ${active > 0 ? alpha(s.accent, 0.25 + 0.6 * active) : alpha(s.ink, s.dark ? 0.12 : 0.1)}`,
        boxShadow: `0 30px 80px rgba(0,0,0,${s.dark ? 0.45 : 0.12})${
          active > 0
            ? `, 0 0 ${60 * active}px ${alpha(s.accent, 0.28 * active)}`
            : ""
        }`,
        backdropFilter: "blur(18px)",
        overflow: "hidden",
        boxSizing: "border-box",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          background: `linear-gradient(180deg, ${alpha("#ffffff", s.dark ? 0.07 : 0.5)} 0%, rgba(255,255,255,0) 35%)`,
          pointerEvents: "none",
        }}
      />
      {children}
    </div>
  );
};
