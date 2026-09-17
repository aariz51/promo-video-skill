import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, dur } from "../theme";
import { KineticWords } from "../components/KineticWords";
import { Particles } from "../components/Particles";
import { bob, pulse, pushIn, tailFade } from "../animations/motion";
import { sPop } from "../animations/springs";

// Scene 1 — Hook. "Every label raises a question." The anxiety, stated calmly.
export const S1_Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;

  const scale = pushIn(frame, 0, dur.hook, 1.06, 1.14); // slow drift in
  const opacity = tailFade(frame, dur.hook, 16);

  // floating question glyph
  const qIn = sPop({ frame, fps, delay: 40 });
  const qFloat = bob(frame, 10, 130);
  const qGlow = pulse(frame, 70);

  return (
    <AbsoluteFill style={{ background: BG_RADIAL }}>
      <Particles count={18} opacity={0.8} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${scale})`,
          opacity,
        }}
      >
        {/* soft question mark hovering above the line */}
        <div
          style={{
            fontFamily: FONT_HEAD,
            fontWeight: 800,
            fontSize: wide ? 120 : 140,
            color: COLORS.purple,
            opacity: interpolate(qIn, [0, 1], [0, 0.9]),
            transform: `translateY(${interpolate(qIn, [0, 1], [30, 0]) + qFloat}px) scale(${interpolate(qIn, [0, 1], [0.6, 1])})`,
            filter: `drop-shadow(0 10px 30px rgba(122,31,162,${0.15 + qGlow * 0.2}))`,
            marginBottom: wide ? 34 : 48,
          }}
        >
          ?
        </div>

        <KineticWords
          startAt={6}
          stagger={7}
          fontSize={wide ? 104 : 96}
          maxWidth={wide ? "62%" : "86%"}
          words={[
            { text: "Every" },
            { text: "day," },
            { text: "the" },
            { text: "same" },
            { text: "question.", color: COLORS.purple },
          ]}
        />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
