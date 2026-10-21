import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sSettle } from "../animations/springs";
import { CubeRise } from "../animations/cube";
import { Ground, PointOfLight } from "../components/Atmosphere";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { asset, useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  name: string;
  line?: string;
  logo?: string;
  cta?: string;
  small?: string;
  _t: { logo: number; name: number; line: number; cta: number };
};

// The hook's point of light returns and contracts into the name; the closing line; a
// hold; fade to ground.
export const Lockup: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const d = scene.durationInFrames;
  const nameAt = f(p._t.name, fps);
  const light = interpolate(frame, [0, nameAt, nameAt + 20], [0.4, 1, 0.35], {
    extrapolateRight: "clamp",
    easing: EASE.inOut,
  });
  const lightSize = interpolate(frame, [0, nameAt + 10], [L.u * 60, L.u * 22], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const k = sSettle({ frame, fps, delay: nameAt });
  const out = interpolate(frame, [d - fps * 0.9, d], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const size = fitSize(p.name, L.u * (L.wide ? 11 : 10), L.contentW, 1, 0.6);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <Ground glow={0.3 + 0.4 * light} />
      <PointOfLight size={lightSize} intensity={light} y={p.logo ? 36 : 42} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
        }}
      >
        {p.logo ? (
          <Img
            src={asset(p.logo)}
            style={{
              height: L.u * 11,
              marginBottom: L.u * 3,
              opacity: sSettle({ frame, fps, delay: f(p._t.logo, fps) }),
            }}
          />
        ) : null}
        <div
          style={{
            fontFamily: FONT_SANS,
            fontWeight: 700,
            fontSize: size,
            color: s.ink,
            letterSpacing: interpolate(k, [0, 1], [size * 0.12, -size * 0.035]),
            opacity: k,
            filter: `blur(${(1 - k) * 8}px)`,
          }}
        >
          {p.name}
        </div>
        {p.line ? (
          <CubeRise at={f(p._t.line, fps)} style={{ marginTop: L.u * 2.6 }}>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: fitSize(p.line, L.u * 3.2, L.contentW, 2),
                color: s.ink,
                opacity: 0.86,
                textAlign: "center",
                maxWidth: L.contentW,
              }}
            >
              {p.line}
            </div>
          </CubeRise>
        ) : null}
        {p.cta ? (
          <CubeRise at={f(p._t.cta, fps)} style={{ marginTop: L.u * 4 }}>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: fitSize(p.cta, L.u * 2.1, L.contentW, 1, 0.62),
                color: s.accent,
              }}
            >
              {p.cta}
            </div>
          </CubeRise>
        ) : null}
      </AbsoluteFill>
      {p.small ? (
        <div
          style={{
            position: "absolute",
            bottom: L.safeY * 0.7,
            width: "100%",
            textAlign: "center",
            fontFamily: FONT_SANS,
            fontSize: L.u * 1.5,
            color: s.inkSoft,
            opacity: interpolate(
              frame,
              [f(p._t.cta, fps), f(p._t.cta, fps) + 20],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            ),
          }}
        >
          {p.small}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
