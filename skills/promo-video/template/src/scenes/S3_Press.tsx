import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, dur } from "../theme";
import { Particles } from "../components/Particles";
import { Cursor } from "../components/Cursor";
import { ActionButton } from "../components/ActionButton";
import { Bloom } from "../components/Bloom";
import { EASE } from "../animations/easings";

const PRESS = 22; // frame the click lands

// Scene 3 — The press. Cursor taps Scan; shockwave; then a dive-zoom that blows
// out to white and hands off to the verdict.
export const S3_Press: React.FC = () => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const cx = width / 2;
  const cy = height * 0.5;

  const pressProg = interpolate(frame, [PRESS, PRESS + 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const pressed = frame >= PRESS && frame <= PRESS + 8 ? 1 : 0;

  // shockwave ring
  const wave = interpolate(frame, [PRESS, PRESS + 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.out,
  });

  // dive: after the press, scale the whole stage up toward camera
  const dive = interpolate(frame, [PRESS + 20, dur.press], [1, 3.4], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.in,
  });

  // cursor rests on the button, lifts slightly after press
  const curX = cx + 120;
  const curY = interpolate(frame, [0, PRESS, PRESS + 20], [cy + 95, cy + 80, cy + 55], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, overflow: "hidden" }}>
      <Particles count={14} opacity={0.6} />

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${dive})`,
        }}
      >
        {/* shockwave */}
        {wave > 0 && wave < 1 && (
          <div
            style={{
              position: "absolute",
              width: wave * 900,
              height: wave * 900,
              borderRadius: "50%",
              border: `${12 - wave * 11}px solid ${COLORS.purple}`,
              opacity: (1 - wave) * 0.75,
            }}
          />
        )}
        <ActionButton size={300} glowStrength={0.5 + pressProg * 0.5} press={pressed} />
      </AbsoluteFill>

      {dive < 1.6 && <Cursor x={curX} y={curY} scale={1.4} pressed={pressProg} />}

      {/* blow out to white to hand off to the verdict */}
      <Bloom frame={frame} peak={dur.press - 6} rise={16} fall={2} />
    </AbsoluteFill>
  );
};
