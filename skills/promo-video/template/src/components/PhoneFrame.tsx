import React, { useState } from "react";
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
  const [failed, setFailed] = useState(false);
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
        {failed ? (
          // A missing screenshot must not cancel a 33s render at frame 1700.
          // Show a labelled placeholder and let the render finish, so the
          // problem is visible in the output instead of fatal.
          <div
            style={{
              width: "100%",
              height: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: screenW * 0.08,
              boxSizing: "border-box",
              textAlign: "center",
              background: `repeating-linear-gradient(45deg, ${COLORS.creamDeep} 0 ${screenW * 0.04}px, ${COLORS.cream} ${screenW * 0.04}px ${screenW * 0.08}px)`,
              color: COLORS.inkSoft,
              fontSize: screenW * 0.07,
              fontWeight: 700,
              lineHeight: 1.3,
              wordBreak: "break-word",
            }}
          >
            {`missing screen\n${src}`}
          </div>
        ) : (
          <Img
            src={staticFile(src)}
            onError={() => {
              // eslint-disable-next-line no-console
              console.warn(
                `[PhoneFrame] could not load "${src}". Check public/${src} exists and that ` +
                  `\`screens\` in src/theme.ts points at it.`,
              );
              setFailed(true);
            }}
            style={{ width: "100%", height: "100%", objectFit: "cover", objectPosition: "top" }}
          />
        )}
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
