import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { sEnter } from "../animations/springs";
import { FONT_SANS } from "../fonts";
import { useStyle } from "../style";

// A headline that builds word by word on a spring stagger. Words listed in `accent`
// are painted in the accent colour: hierarchy without changing size.
export const KineticWords: React.FC<{
  text: string;
  accent?: string[];
  fontSize: number;
  startAt?: number; // local frame
  stagger?: number; // frames between words
  weight?: number;
  maxWidth?: number | string;
  align?: "center" | "left";
  color?: string;
  lineHeight?: number;
}> = ({
  text,
  accent = [],
  fontSize,
  startAt = 0,
  stagger = 4,
  weight = 600,
  maxWidth = "100%",
  align = "center",
  color,
  lineHeight = 1.08,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = useStyle();
  const marks = new Set(
    accent.map((a) => a.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "")),
  );
  const words = text.split(/\s+/).filter(Boolean);
  // Balanced wrapping: when the line must wrap, narrow the box so the lines come out
  // even instead of leaving one orphaned word.
  let width = maxWidth;
  if (typeof maxWidth === "number") {
    const est = text.length * 0.54 * fontSize;
    const lines = Math.ceil(est / maxWidth);
    if (lines > 1) width = Math.min(maxWidth, (est / lines) * 1.12);
  }
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: align === "center" ? "center" : "flex-start",
        gap: `${fontSize * 0.12}px ${fontSize * 0.26}px`,
        maxWidth: width,
        margin: align === "center" ? "0 auto" : undefined,
        fontFamily: FONT_SANS,
        fontWeight: weight,
        fontSize,
        lineHeight,
        letterSpacing: -fontSize * 0.028,
        textAlign: align,
      }}
    >
      {words.map((w, i) => {
        const p = sEnter({ frame, fps, delay: startAt + i * stagger });
        const key = w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              color: marks.has(key) ? s.accent : (color ?? s.ink),
              opacity: interpolate(p, [0, 1], [0, 1]),
              transform: `translateY(${interpolate(p, [0, 1], [fontSize * 0.35, 0])}px)`,
              filter: `blur(${interpolate(p, [0, 1], [8, 0])}px)`,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};
