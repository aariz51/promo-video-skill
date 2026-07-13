import React from "react";
import { Img, staticFile } from "remotion";
import { SCREEN_RATIO, COLORS } from "../theme";

// A clean rounded iPhone with a real app screenshot inside, dynamic island,
// and an optional brand glow. Width-driven; height derives from screen ratio.
export const PhoneFrame: React.FC<{
  src: string;
  width: number;
  glow?: string;
  radius?: number;
  bezel?: number;
  shadow?: boolean;
}> = ({ src, width, glow, radius, bezel, shadow = true }) => {
  const b = bezel ?? Math.max(8, width * 0.03);
  const r = radius ?? width * 0.14;
  const screenW = width - b * 2;
  const screenH = screenW / SCREEN_RATIO;
  const height = screenH + b * 2;

  return (
    <div
      style={{
        width,
        height,
        borderRadius: r,
        background: "linear-gradient(160deg, #2A2C3A 0%, #14151E 100%)",
        padding: b,
        boxSizing: "border-box",
        position: "relative",
        boxShadow: shadow
          ? `0 50px 110px rgba(43,45,66,0.34)${glow ? `, 0 0 90px ${glow}` : ""}`
          : glow
            ? `0 0 90px ${glow}`
            : undefined,
      }}
    >
      <div
        style={{
          width: screenW,
          height: screenH,
          borderRadius: r - b,
          overflow: "hidden",
          position: "relative",
          background: COLORS.cream,
        }}
      >
        <Img
          src={staticFile(src)}
          style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }}
        />
      </div>
      {/* dynamic island */}
      <div
        style={{
          position: "absolute",
          top: b + screenH * 0.018,
          left: "50%",
          transform: "translateX(-50%)",
          width: screenW * 0.30,
          height: screenW * 0.085,
          borderRadius: 100,
          background: "#0B0C12",
        }}
      />
    </div>
  );
};
