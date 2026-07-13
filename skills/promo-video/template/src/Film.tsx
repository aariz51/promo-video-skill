import React from "react";
import { AbsoluteFill, Sequence, Audio, staticFile } from "remotion";
import { COLORS, T, dur, AUDIO_SRC } from "./theme";
import { FontLoader } from "./components/FontLoader";
import { S1_Hook } from "./scenes/S1_Hook";
import { S2_OneTap } from "./scenes/S2_OneTap";
import { S3_Press } from "./scenes/S3_Press";
import { S4_Verdict } from "./scenes/S4_Verdict";
import { S5_MoreThanScan } from "./scenes/S5_MoreThanScan";
import { S6_DeviceOrbit } from "./scenes/S6_DeviceOrbit";
import { S7_Dashboard } from "./scenes/S7_Dashboard";
import { S8_Tagline } from "./scenes/S8_Tagline";
import { S9_Logo } from "./scenes/S9_Logo";

// The master film: 9 movements over 33s. Timing lives in theme.ts (`T`/`dur`) and
// is shared by the audio builder, so VO + SFX stay frame-synced across every
// orientation. This is the reference implementation — swap scene copy, screens,
// colours and VO for your app; keep the timing and motion language.
export const Film: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.cream }}>
      <FontLoader />
      <Sequence from={T.hook} durationInFrames={dur.hook}>
        <S1_Hook />
      </Sequence>
      <Sequence from={T.oneTap} durationInFrames={dur.oneTap}>
        <S2_OneTap />
      </Sequence>
      <Sequence from={T.press} durationInFrames={dur.press}>
        <S3_Press />
      </Sequence>
      <Sequence from={T.verdict} durationInFrames={dur.verdict}>
        <S4_Verdict />
      </Sequence>
      <Sequence from={T.more} durationInFrames={dur.more}>
        <S5_MoreThanScan />
      </Sequence>
      <Sequence from={T.orbit} durationInFrames={dur.orbit}>
        <S6_DeviceOrbit />
      </Sequence>
      <Sequence from={T.dashboard} durationInFrames={dur.dashboard}>
        <S7_Dashboard />
      </Sequence>
      <Sequence from={T.tagline} durationInFrames={dur.tagline}>
        <S8_Tagline />
      </Sequence>
      <Sequence from={T.logo} durationInFrames={dur.logo}>
        <S9_Logo />
      </Sequence>

      {/* Single pre-mixed master: VO + SFX + soft ambient pad (no music), one
          continuous file — no multi-clip stutter. Built by scripts/build_audio.py.
          Set AUDIO_SRC = null in theme.ts to preview silently before it exists. */}
      {AUDIO_SRC ? <Audio src={staticFile(AUDIO_SRC)} /> : null}
    </AbsoluteFill>
  );
};
