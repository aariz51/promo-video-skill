import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, dur } from "../theme";
import { Particles } from "../components/Particles";
import { Bloom } from "../components/Bloom";
import { Cursor } from "../components/Cursor";
import { ActionButton } from "../components/ActionButton";
import { sEnter, sPop } from "../animations/springs";
import { bob, pulse, tailFade } from "../animations/motion";
import { EASE } from "../animations/easings";

// Scene 2 — "One tap. Zero doubt." The promise + the glowing scan button.
export const S2_OneTap: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;

  const cx = width / 2;
  const btnY = wide ? height * 0.64 : height * 0.6;

  const l1 = sEnter({ frame, fps, delay: 8 });
  const l2 = sEnter({ frame, fps, delay: 16 });
  const btn = sPop({ frame, fps, delay: 26 });
  const float = bob(frame, 8, 120);
  const glow = pulse(frame, 46);
  const opacity = tailFade(frame, dur.oneTap, 12);

  // cursor drifts in from bottom-right toward the button
  const curX = interpolate(frame, [30, dur.oneTap], [width + 120, cx + 90], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const curY = interpolate(frame, [30, dur.oneTap], [height + 120, btnY + 70], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity }}>
      <Particles count={16} opacity={0.7} />

      {/* headline */}
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: wide ? height * 0.16 : height * 0.2 }}>
        <div
          style={{
            fontFamily: FONT_HEAD,
            fontWeight: 700,
            fontSize: wide ? 100 : 112,
            letterSpacing: -2,
            textAlign: "center",
            lineHeight: 1.05,
          }}
        >
          <span
            style={{
              display: "inline-block",
              color: COLORS.ink,
              opacity: l1,
              transform: `translateY(${interpolate(l1, [0, 1], [40, 0])}px)`,
            }}
          >
            One tap.
          </span>
          <br />
          <span
            style={{
              display: "inline-block",
              color: COLORS.purple,
              opacity: l2,
              transform: `translateY(${interpolate(l2, [0, 1], [40, 0])}px)`,
            }}
          >
            Zero doubt.
          </span>
        </div>
      </AbsoluteFill>

      {/* scan button */}
      <div
        style={{
          position: "absolute",
          left: cx,
          top: btnY + float,
          transform: `translate(-50%, -50%) scale(${interpolate(btn, [0, 1], [0.3, 1])})`,
        }}
      >
        <ActionButton size={300} glowStrength={0.4 + glow * 0.5} />
      </div>

      <Cursor x={curX} y={curY} scale={1.4} />
      <Bloom frame={frame} peak={6} rise={6} fall={16} />
    </AbsoluteFill>
  );
};
