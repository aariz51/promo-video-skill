import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, dur } from "../theme";
import { Particles } from "../components/Particles";
import { sPop } from "../animations/springs";
import { tailFade } from "../animations/motion";

// Scene 8 — "Scan. Know. Protect." Period-rhythm, keyword-colored, on-beat pops.
export const S8_Tagline: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;
  const opacity = tailFade(frame, dur.tagline, 14);

  const words = [
    { t: "Ask.", c: COLORS.purple },
    { t: "Know.", c: COLORS.pink },
    { t: "Move.", c: COLORS.gold },
  ];
  const beat = 16; // frames between beats

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity, justifyContent: "center", alignItems: "center" }}>
      <Particles count={16} opacity={0.7} />
      <div
        style={{
          display: "flex",
          flexDirection: wide ? "row" : "column",
          gap: wide ? 34 : 18,
          alignItems: wide ? "baseline" : "center",
        }}
      >
        {words.map((w, i) => {
          const s = sPop({ frame, fps, delay: 8 + i * beat });
          return (
            <span
              key={i}
              style={{
                fontFamily: FONT_HEAD,
                fontWeight: 800,
                fontSize: wide ? 140 : 168,
                letterSpacing: wide ? -2 : -3,
                lineHeight: 1,
                color: w.c,
                display: "inline-block",
                opacity: s,
                transform: `translateY(${interpolate(s, [0, 1], [wide ? 50 : 60, 0])}px) scale(${interpolate(s, [0, 1], [0.6, 1])})`,
                filter: `drop-shadow(0 14px 34px ${w.c}44)`,
              }}
            >
              {w.t}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
