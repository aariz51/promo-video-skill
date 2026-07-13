import React from "react";
import { COLORS } from "../theme";

// Glassmorphic floating prop — the reference's frosted UI card, re-skinned warm.
// Semi-transparent brand gradient, ambient shadow, soft inner highlight.
export const GlassCard: React.FC<{
  width: number;
  height: number;
  tint?: string;
  radius?: number;
  glow?: string;
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({
  width,
  height,
  tint = COLORS.purple,
  radius = 34,
  glow,
  children,
  style,
}) => {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: radius,
        position: "relative",
        background: `linear-gradient(155deg, ${tint}E6 0%, ${tint}B3 55%, ${tint}80 100%)`,
        boxShadow: `0 40px 90px ${tint}40, 0 8px 30px rgba(43,45,66,0.12)${
          glow ? `, 0 0 80px ${glow}` : ""
        }`,
        overflow: "hidden",
        ...style,
      }}
    >
      {/* top inner highlight */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          background:
            "linear-gradient(180deg, rgba(255,255,255,0.35) 0%, rgba(255,255,255,0) 30%)",
          pointerEvents: "none",
        }}
      />
      {/* subtle border */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: radius,
          border: "1.5px solid rgba(255,255,255,0.35)",
          pointerEvents: "none",
        }}
      />
      {children}
    </div>
  );
};
