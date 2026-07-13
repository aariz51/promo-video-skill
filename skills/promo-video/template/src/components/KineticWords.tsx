import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, FONT_HEAD } from "../theme";
import { sEnter } from "../animations/springs";

export type Word = { text: string; color?: string };

// The signature reference technique: a centered headline built word-by-word with
// a spring stagger, each value-word painted in a brand hue. Words wrap; each
// gets its own delayed pop-in (position + scale + opacity together).
export const KineticWords: React.FC<{
  words: Word[];
  fontSize?: number;
  weight?: number;
  startAt?: number; // local frame to begin
  stagger?: number; // frames between words
  lineHeight?: number;
  gap?: number;
  maxWidth?: number | string;
  letterSpacing?: number;
}> = ({
  words,
  fontSize = 96,
  weight = 700,
  startAt = 0,
  stagger = 6,
  lineHeight = 1.1,
  gap = 0.28,
  maxWidth = "78%",
  letterSpacing = -1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "center",
        gap: `${gap * 0.4}em ${gap}em`,
        maxWidth,
        margin: "0 auto",
        fontFamily: FONT_HEAD,
        fontWeight: weight,
        fontSize,
        lineHeight,
        letterSpacing,
        textAlign: "center",
      }}
    >
      {words.map((w, i) => {
        const s = sEnter({ frame, fps, delay: startAt + i * stagger });
        const y = interpolate(s, [0, 1], [46, 0]);
        const op = interpolate(s, [0, 1], [0, 1]);
        const sc = interpolate(s, [0, 1], [0.82, 1]);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              color: w.color ?? COLORS.ink,
              opacity: op,
              transform: `translateY(${y}px) scale(${sc})`,
            }}
          >
            {w.text}
          </span>
        );
      })}
    </div>
  );
};
