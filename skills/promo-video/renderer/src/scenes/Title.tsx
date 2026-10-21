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
import { Ground } from "../components/Atmosphere";
import { FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { asset, useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  name: string;
  tagline?: string;
  logo?: string;
  _t: { name: number; tagline: number };
};

// The name lands in silence: tracking closes, a band of light crosses the letters.
export const Title: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const at = f(p._t.name, fps);
  const k = sSettle({ frame, fps, delay: at });
  const size = fitSize(p.name, L.u * (L.wide ? 15 : 13), L.contentW, 1, 0.6);
  const sweep = interpolate(frame, [at + 6, at + 40], [-30, 130], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.inOut,
  });
  const push = interpolate(frame, [0, scene.durationInFrames], [1, 1.04]);
  return (
    <AbsoluteFill>
      <Ground glow={0.6} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          transform: `scale(${push})`,
        }}
      >
        {p.logo ? (
          <Img
            src={asset(p.logo)}
            style={{
              height: L.u * 12,
              marginBottom: L.u * 3,
              opacity: k,
              transform: `scale(${0.9 + 0.1 * k})`,
            }}
          />
        ) : null}
        <div
          style={{
            fontFamily: FONT_SANS,
            fontWeight: 700,
            fontSize: size,
            letterSpacing: interpolate(k, [0, 1], [size * 0.2, -size * 0.035]),
            lineHeight: 1,
            opacity: k,
            filter: `blur(${(1 - k) * 10}px)`,
            backgroundImage: `linear-gradient(100deg, ${s.ink} ${sweep - 12}%, #ffffff ${sweep}%, ${s.ink} ${sweep + 12}%)`,
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: "transparent",
            whiteSpace: "nowrap",
          }}
        >
          {p.name}
        </div>
        {p.tagline ? (
          <CubeRise at={f(p._t.tagline, fps)} style={{ marginTop: L.u * 3 }}>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: fitSize(p.tagline, L.u * 3.4, L.contentW, 2),
                color: s.inkSoft,
                fontWeight: 450,
                textAlign: "center",
                maxWidth: L.contentW,
              }}
            >
              {p.tagline}
            </div>
          </CubeRise>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
