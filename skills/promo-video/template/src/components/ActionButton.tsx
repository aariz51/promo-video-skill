import React from "react";
import { COLORS, FONT_HEAD } from "../theme";

// The primary action button — glassy brand-colour orb with a reticle glyph.
// Reused in the "One tap" and "Press" scenes.
export const ActionButton: React.FC<{
  size?: number;
  glowStrength?: number; // 0..1
  press?: number; // 0..1 pressed-down
}> = ({ size = 230, glowStrength = 0.6, press = 0 }) => {
  const s = size * (1 - press * 0.08);
  return (
    <div
      style={{
        width: s,
        height: s,
        borderRadius: "50%",
        background: `radial-gradient(circle at 36% 30%, ${COLORS.purpleSoft} 0%, ${COLORS.purple} 60%, ${COLORS.purpleDeep} 100%)`,
        boxShadow: `0 30px 70px rgba(122,31,162,0.45), 0 0 ${40 + glowStrength * 90}px rgba(122,31,162,${0.35 + glowStrength * 0.4})`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
      }}
    >
      {/* inner highlight */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: "linear-gradient(180deg, rgba(255,255,255,0.3) 0%, rgba(255,255,255,0) 40%)",
        }}
      />
      <svg width={s * 0.42} height={s * 0.42} viewBox="0 0 100 100" fill="none">
        <path
          d="M14 32 V20 a6 6 0 0 1 6 -6 H32 M68 14 H80 a6 6 0 0 1 6 6 V32 M86 68 V80 a6 6 0 0 1 -6 6 H68 M32 86 H20 a6 6 0 0 1 -6 -6 V68"
          stroke="#fff"
          strokeWidth="7"
          strokeLinecap="round"
        />
        <rect x="24" y="46" width="52" height="8" rx="4" fill="#fff" />
      </svg>
      <div
        style={{
          fontFamily: FONT_HEAD,
          fontWeight: 800,
          fontSize: s * 0.13,
          letterSpacing: 1,
          color: "#fff",
          marginTop: s * 0.04,
        }}
      >
        SCAN
      </div>
    </div>
  );
};
