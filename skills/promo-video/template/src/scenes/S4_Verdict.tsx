import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, FONT_BODY, dur } from "../theme";
import { ScoreRing } from "../components/ScoreRing";
import { Confetti } from "../components/Confetti";
import { Particles } from "../components/Particles";
import { sEnter, sBounce } from "../animations/springs";
import { tailFade } from "../animations/motion";

const RING_START = 14;
const RING_SPAN = 52;
const REWARD = RING_START + RING_SPAN - 4; // confetti + pill when the ring lands

// Scene 4 — Scan → verdict. The emotional peak. The signature safety gauge sweeps
// to 92, a SAFE verdict springs, confetti rewards. Abstract, like the reference's
// "94/100 / Done" beats — no contradicting screenshot, pure proof.
export const S4_Verdict: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;
  const ringSize = wide ? 420 : 560;

  const bloomRecover = interpolate(frame, [0, 14], [1, 0], { extrapolateRight: "clamp" });
  const opacity = tailFade(frame, dur.verdict, 14);

  const eyebrow = sEnter({ frame, fps, delay: 6 });
  const product = sEnter({ frame, fps, delay: 12 });
  const pill = sBounce({ frame, fps, delay: REWARD });

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity }}>
      <Particles count={16} opacity={0.55} />

      <AbsoluteFill style={{ flexDirection: "column", alignItems: "center", justifyContent: "center", gap: wide ? 20 : 30 }}>
        {/* eyebrow — the "we are done thinking" cue */}
        <div
          style={{
            opacity: eyebrow,
            transform: `translateY(${interpolate(eyebrow, [0, 1], [24, 0])}px)`,
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "12px 26px",
            borderRadius: 100,
            background: "rgba(47,181,106,0.12)",
            border: `1.5px solid ${COLORS.safe}44`,
          }}
        >
          <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
            <path d="M5 13l4 4L19 7" stroke={COLORS.safe} strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={{ fontFamily: FONT_BODY, fontWeight: 700, fontSize: 30, color: COLORS.safe, letterSpacing: 2 }}>
            ANSWER READY
          </span>
        </div>

        {/* product name */}
        <div
          style={{
            opacity: product,
            transform: `translateY(${interpolate(product, [0, 1], [24, 0])}px)`,
            fontFamily: FONT_HEAD,
            fontWeight: 800,
            fontSize: wide ? 48 : 62,
            color: COLORS.ink,
            letterSpacing: -1,
            textAlign: "center",
          }}
        >
          Organic Oat Cereal
        </div>

        {/* signature score gauge */}
        <ScoreRing
          frame={frame}
          score={92}
          size={ringSize}
          stroke={wide ? 26 : 34}
          color={COLORS.safe}
          trackColor="rgba(47,181,106,0.16)"
          start={RING_START}
          span={RING_SPAN}
        />

        {/* verdict pill */}
        <div
          style={{
            transform: `scale(${interpolate(pill, [0, 1], [0.5, 1])})`,
            opacity: pill,
            background: COLORS.safe,
            color: "#fff",
            fontFamily: FONT_HEAD,
            fontWeight: 800,
            fontSize: wide ? 44 : 56,
            letterSpacing: 0.5,
            padding: wide ? "16px 48px" : "22px 62px",
            borderRadius: 100,
            boxShadow: `0 26px 60px rgba(47,181,106,0.42)`,
            display: "flex",
            alignItems: "center",
            gap: 18,
          }}
        >
          <svg width={wide ? 38 : 46} height={wide ? 38 : 46} viewBox="0 0 24 24" fill="none">
            <path d="M5 13l4 4L19 7" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          ALL CLEAR
        </div>
      </AbsoluteFill>

      <Confetti frame={frame} start={REWARD} count={110} />

      {/* recover from S3's white blow-out */}
      <AbsoluteFill style={{ background: "#fff", opacity: bloomRecover, pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};
