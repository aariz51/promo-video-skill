import React from "react";
import { AbsoluteFill, Img, staticFile, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, FONT_BODY, LOGO } from "../theme";
import { Particles } from "../components/Particles";
import { Bloom } from "../components/Bloom";
import { sPop, sSettle } from "../animations/springs";
import { pulse } from "../animations/motion";

// A resting-heartbeat pulse: a lub-dub every ~50 frames.
const heartbeat = (f: number) => {
  const p = f % 50;
  const lub = Math.max(0, 1 - Math.abs(p - 6) / 6);
  const dub = Math.max(0, 1 - Math.abs(p - 16) / 6);
  return lub * 0.9 + dub * 0.55;
};

const StoreBadge: React.FC<{ top: string; bottom: string; delay: number }> = ({ top, bottom, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = sPop({ frame, fps, delay });
  return (
    <div
      style={{
        transform: `translateY(${interpolate(s, [0, 1], [40, 0])}px)`,
        opacity: s,
        background: COLORS.ink,
        color: "#fff",
        borderRadius: 18,
        padding: "16px 30px",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        minWidth: 220,
      }}
    >
      <div style={{ fontFamily: FONT_BODY, fontSize: 18, opacity: 0.8 }}>{top}</div>
      <div style={{ fontFamily: FONT_HEAD, fontWeight: 800, fontSize: 32 }}>{bottom}</div>
    </div>
  );
};

// Scene 9 — Logo lockup. The app logo lands as a soft rounded
// tile, pulses like a heartbeat, then the tagline + store badges resolve.
export const S9_Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;

  const mark = sPop({ frame, fps, delay: 6 });
  const beat = heartbeat(frame);
  const logoScale = interpolate(mark, [0, 1], [0.4, 1]) * (1 + beat * 0.05);
  const glow = pulse(frame, 60);

  const tag = sSettle({ frame, fps, delay: 26 });
  const LOGO_SIZE = wide ? 500 : 680;

  return (
    <AbsoluteFill
      style={{
        background: BG_RADIAL,
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <Particles count={20} opacity={0.8} />

      {/* soft ambient halo — wider than the logo so there's no hard ring */}
      <div
        style={{
          position: "absolute",
          top: wide ? "14%" : "26%",
          width: wide ? 720 : 980,
          height: wide ? 720 : 980,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.pinkSoft}44 0%, rgba(247,224,230,0) 62%)`,
          transform: `scale(${0.92 + glow * 0.14 + beat * 0.12})`,
        }}
      />

      {/* real app logo as a rounded tile with the heartbeat pulse */}
      <div
        style={{
          opacity: mark,
          transform: `scale(${logoScale})`,
          borderRadius: LOGO_SIZE * 0.14,
          overflow: "hidden",
          boxShadow:
            "0 40px 90px rgba(122,31,162,0.18), 0 14px 36px rgba(43,45,66,0.14)",
          marginBottom: 44,
        }}
      >
        <Img
          src={staticFile(LOGO)}
          style={{ width: LOGO_SIZE, height: LOGO_SIZE, display: "block" }}
        />
      </div>

      {/* tagline */}
      <div
        style={{
          fontFamily: FONT_BODY,
          fontWeight: 500,
          fontSize: 42,
          color: COLORS.inkSoft,
          opacity: tag,
          transform: `translateY(${interpolate(tag, [0, 1], [24, 0])}px)`,
          textAlign: "center",
        }}
      >
        Your one-line product tagline
      </div>

      {/* store badges */}
      <div style={{ display: "flex", gap: 28, marginTop: 46 }}>
        <StoreBadge top="Download on the" bottom="App Store" delay={40} />
        <StoreBadge top="GET IT ON" bottom="Google Play" delay={48} />
      </div>

      <Bloom frame={frame} peak={5} rise={6} fall={16} />
    </AbsoluteFill>
  );
};
