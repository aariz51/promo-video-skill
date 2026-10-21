import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { KineticWords } from "../components/KineticWords";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  text: string;
  accent?: string[];
  eyebrow?: string;
  small?: string;
  size?: "xl" | "l" | "m";
  _t: { text: number; small: number };
};

// One large line, when the words are the subject. Rare by design.
export const Statement: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const base =
    { xl: 8.6, l: 6.8, m: 5.2 }[p.size ?? "l"] * L.u * (L.wide ? 1 : 1.05);
  const size = fitSize(
    p.text,
    base,
    L.contentW * (L.wide ? 0.82 : 1),
    L.wide ? 2 : 4,
  );
  const push = interpolate(frame, [0, scene.durationInFrames], [1, 1.05]);
  return (
    <AbsoluteFill>
      <Ground glow={0.35} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: `0 ${L.safeX}px`,
          transform: `scale(${push})`,
        }}
      >
        {p.eyebrow ? (
          <CubeRise at={f(p._t.text, fps)} style={{ marginBottom: L.u * 3 }}>
            <div
              style={{
                fontFamily: FONT_MONO,
                fontSize: L.u * 1.7,
                color: s.accent,
                letterSpacing: L.u * 0.35,
                textTransform: "uppercase",
              }}
            >
              {p.eyebrow}
            </div>
          </CubeRise>
        ) : null}
        <KineticWords
          text={p.text}
          accent={p.accent}
          fontSize={size}
          startAt={f(p._t.text, fps)}
          maxWidth={L.contentW * (L.wide ? 0.82 : 1)}
        />
        {p.small ? (
          <CubeRise at={f(p._t.small, fps)} style={{ marginTop: L.u * 4 }}>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: fitSize(p.small, L.u * 2.1, L.contentW * 0.8, 2),
                color: s.inkSoft,
                textAlign: "center",
                maxWidth: L.contentW * 0.8,
              }}
            >
              {p.small}
            </div>
          </CubeRise>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
