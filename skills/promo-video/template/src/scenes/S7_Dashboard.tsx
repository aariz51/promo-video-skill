import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, FONT_BODY, screens, dur } from "../theme";
import { PhoneFrame } from "../components/PhoneFrame";
import { Particles } from "../components/Particles";
import { Bloom } from "../components/Bloom";
import { Cursor } from "../components/Cursor";
import { GlassCard } from "../components/GlassCard";
import { sEnter, sPop } from "../animations/springs";
import { bob, tailFade } from "../animations/motion";
import { EASE } from "../animations/easings";

const TAP = 96; // frame the cursor taps

// Scene 7 — "One calm place." The real dashboard rises from perspective; a cursor
// taps; a reassuring health callout floats. Portrait: phone centred, headline top.
// Landscape: phone left, headline right.
export const S7_Dashboard: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;
  const opacity = tailFade(frame, dur.dashboard, 16);

  const enter = sEnter({ frame, fps, delay: 6 });
  const rotX = interpolate(enter, [0, 1], [20, 3], { easing: EASE.out });
  const rotZ = interpolate(enter, [0, 1], [5, -1.5]);
  const phoneY = bob(frame, 8, 150);

  const title = sEnter({ frame, fps, delay: 18 });
  const chip = sPop({ frame, fps, delay: 44 });

  const phoneW = wide ? 440 : 500;
  const phoneCx = wide ? width * 0.32 : width / 2;
  const phoneCy = wide ? height * 0.54 : height * 0.58;

  // cursor travels in and taps the primary call-to-action
  const curX = interpolate(frame, [10, TAP], [width + 120, phoneCx + (wide ? 30 : 40)], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const curY = interpolate(frame, [10, TAP], [height + 140, phoneCy + (wide ? 200 : 240)], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const press = interpolate(frame, [TAP, TAP + 10, TAP + 22], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity }}>
      <Particles count={18} opacity={0.55} />

      {/* headline */}
      {wide ? (
        <div
          style={{
            position: "absolute",
            left: width * 0.72,
            top: height * 0.52,
            transform: `translate(-50%, -50%) translateY(${interpolate(title, [0, 1], [40, 0])}px)`,
            opacity: title,
            fontFamily: FONT_HEAD,
            fontWeight: 800,
            fontSize: 92,
            letterSpacing: -2,
            color: COLORS.ink,
            textAlign: "center",
          }}
        >
          One <span style={{ color: COLORS.purple }}>calm</span> place.
        </div>
      ) : (
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: height * 0.11 }}>
          <div
            style={{
              fontFamily: FONT_HEAD,
              fontWeight: 800,
              fontSize: 100,
              letterSpacing: -2,
              color: COLORS.ink,
              textAlign: "center",
              opacity: title,
              transform: `translateY(${interpolate(title, [0, 1], [40, 0])}px)`,
            }}
          >
            One <span style={{ color: COLORS.purple }}>calm</span> place.
          </div>
        </AbsoluteFill>
      )}

      {/* dashboard phone */}
      <div
        style={{
          position: "absolute",
          left: phoneCx,
          top: phoneCy + phoneY,
          transform: `translate(-50%, -50%) perspective(1600px) rotateX(${rotX}deg) rotateZ(${rotZ}deg) scale(${interpolate(enter, [0, 1], [0.85, 1])})`,
          opacity: enter,
        }}
      >
        <PhoneFrame src={screens.dashboard} width={phoneW} glow="rgba(122,31,162,0.3)" />
      </div>

      {/* floating reassurance callout — qualitative, on-message (no contradicting number) */}
      <div
        style={{
          position: "absolute",
          left: wide ? width * 0.72 : width * 0.5,
          top: (wide ? height * 0.24 : height * 0.26) + bob(frame, 10, 120, 1),
          transform: `translateX(${wide ? "-50%" : "0"}) scale(${interpolate(chip, [0, 1], [0.5, 1])})`,
          opacity: chip,
          zIndex: 50,
        }}
      >
        <GlassCard width={300} height={130} tint={COLORS.pink} glow={`${COLORS.pink}55`} radius={30}>
          <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", gap: 18, padding: "0 26px" }}>
            <svg width="52" height="48" viewBox="0 0 24 22" fill="none">
              <path d="M12 20S2 13.5 2 7.2C2 4 4.4 2 7.2 2 9.1 2 10.8 3 12 4.6 13.2 3 14.9 2 16.8 2 19.6 2 22 4 22 7.2 22 13.5 12 20 12 20Z" fill="#fff" />
            </svg>
            <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.05 }}>
              <div style={{ fontFamily: FONT_HEAD, fontWeight: 800, fontSize: 40, color: "#fff" }}>On track</div>
              <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 24, color: "rgba(255,255,255,0.92)" }}>
                this week
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      <Cursor x={curX} y={curY} scale={1.6} pressed={press} />
      <Bloom frame={frame} peak={5} rise={6} fall={14} />
    </AbsoluteFill>
  );
};
