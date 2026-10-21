import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { sEnter } from "../animations/springs";
import { CubeList, CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { GlassCard } from "../components/GlassCard";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type Side = { title: string; items: string[] };
type P = {
  left: Side;
  right: Side;
  title?: string;
  verdict?: string;
  _t: { left: number; right: number; verdict?: number };
};

// Two paths: the usual way (muted) against this product's way (lit). Only factual rows.
export const Compare: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const colW = L.wide ? (L.contentW - L.u * 4) / 2 : L.contentW;
  const all = [...p.left.items, ...p.right.items];
  const itemSize = Math.min(
    ...all.map((t) => fitSize(t, L.u * 2.5, colW * 0.8, 1)),
  );
  const side = (sd: Side, at: number, lit: boolean) => {
    const k = sEnter({ frame, fps, delay: f(at, fps) });
    return (
      <GlassCard
        width={colW}
        radius={L.u * 1.8}
        active={lit ? k : 0}
        fill={lit ? k * 0.6 : 0}
        style={{
          padding: L.u * 3,
          opacity: (lit ? 1 : 0.55) * k,
          transform: `translateY(${(1 - k) * L.u * 3}px)`,
        }}
      >
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: L.u * 1.6,
            letterSpacing: L.u * 0.25,
            textTransform: "uppercase",
            color: lit ? s.accent : s.inkSoft,
            marginBottom: L.u * 2,
          }}
        >
          {sd.title}
        </div>
        <CubeList
          at={f(at, fps) + 6}
          style={{ display: "flex", flexDirection: "column", gap: L.u * 1.3 }}
        >
          {sd.items.map((t, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: L.u * 1.2,
                alignItems: "baseline",
                fontFamily: FONT_SANS,
                fontSize: itemSize,
                color: lit ? s.ink : s.inkSoft,
                textDecoration: lit
                  ? undefined
                  : `line-through ${alpha(s.inkSoft, 0.4)}`,
              }}
            >
              <span style={{ color: lit ? s.accent : s.inkSoft }}>
                {lit ? "●" : "○"}
              </span>
              <span>{t}</span>
            </div>
          ))}
        </CubeList>
      </GlassCard>
    );
  };
  return (
    <AbsoluteFill>
      <Ground glow={0.4} />
      <AbsoluteFill
        style={{
          padding: `${L.safeY}px ${L.safeX}px`,
          justifyContent: "center",
          alignItems: "center",
          gap: L.u * 3.5,
        }}
      >
        {p.title ? (
          <div
            style={{
              fontFamily: FONT_SANS,
              fontWeight: 650,
              fontSize: fitSize(p.title, L.u * 3.8, L.contentW, 1),
              color: s.ink,
              opacity: interpolate(frame, [0, 12], [0, 1], {
                extrapolateRight: "clamp",
              }),
            }}
          >
            {p.title}
          </div>
        ) : null}
        <div
          style={{
            display: "flex",
            flexDirection: L.wide ? "row" : "column",
            gap: L.u * 4,
          }}
        >
          {side(p.left, p._t.left, false)}
          {side(p.right, p._t.right, true)}
        </div>
        {p.verdict && p._t.verdict !== undefined ? (
          <CubeRise at={f(p._t.verdict, fps)}>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontWeight: 650,
                fontSize: fitSize(p.verdict, L.u * 3.4, L.contentW, 2),
                color: s.ink,
                textAlign: "center",
              }}
            >
              {p.verdict}
            </div>
          </CubeRise>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
