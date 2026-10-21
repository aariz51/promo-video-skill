import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { bob, seed } from "../animations/motion";
import { sEnter } from "../animations/springs";
import { Ground } from "../components/Atmosphere";
import { GlassCard } from "../components/GlassCard";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { asset, useStyle } from "../style";
import type { Scene } from "../types";

type Item = { media?: string; label?: string };
type P = {
  items: Item[];
  title?: string;
  layout?: "orbit" | "stack" | "grid" | "row";
  _media?: Record<string, number>;
  _t: { items: number[] };
};

// Range in one image: many real surfaces at once, in depth. Orbit turns slowly; stack
// fans; grid settles. Placement is seeded, never random.
export const Montage: React.FC<{ scene: Scene; seedBase: number }> = ({
  scene,
  seedBase,
}) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const n = p.items.length;
  const layout = p.layout ?? "orbit";
  const cardW = L.wide ? L.width * 0.2 : L.width * 0.36;
  const turn = interpolate(frame, [0, scene.durationInFrames], [0, 0.9]);
  // Row: every item at one shared height, side by side, so mixed aspect ratios line up.
  const aspects = p.items.map((it) =>
    it.media ? (p._media?.[it.media] ?? 16 / 10) : 16 / 10,
  );
  const rowGap = L.u * 3;
  const rowH = Math.min(
    L.height * 0.5,
    (L.contentW - rowGap * (n - 1)) / aspects.reduce((a, b) => a + b, 0),
  );
  const rowTotal = aspects.reduce((a, b) => a + b * rowH, 0) + rowGap * (n - 1);
  return (
    <AbsoluteFill>
      <Ground glow={0.5} />
      <AbsoluteFill style={{ perspective: 2200 }}>
        {p.items.map((it, i) => {
          const k = sEnter({ frame, fps, delay: f(p._t.items[i], fps) });
          const aspect = aspects[i];
          const w = layout === "row" ? rowH * aspect : cardW;
          let x = 0;
          let y = 0;
          let z = 0;
          let rot = 0;
          if (layout === "orbit") {
            const a = (i / n) * Math.PI * 2 + turn;
            x = Math.sin(a) * L.width * (L.wide ? 0.33 : 0.3);
            z = Math.cos(a) * L.u * 30 - L.u * 10;
            y = Math.sin(a * 2 + seedBase) * L.u * 4;
            rot = -Math.sin(a) * 28;
          } else if (layout === "stack") {
            const c = i - (n - 1) / 2;
            x = c * cardW * 0.42;
            y = Math.abs(c) * L.u * 2.2;
            rot = c * 5;
            z = -Math.abs(c) * L.u * 6;
          } else if (layout === "row") {
            const before = aspects
              .slice(0, i)
              .reduce((a, b) => a + b * rowH + rowGap, 0);
            x = -rowTotal / 2 + before + w / 2;
            z = 0;
          } else {
            const cols = L.wide ? Math.min(4, Math.ceil(n / 2)) : 2;
            const r = Math.floor(i / cols);
            const c = i % cols;
            const rows = Math.ceil(n / cols);
            x = (c - (cols - 1) / 2) * cardW * 1.12;
            y = (r - (rows - 1) / 2) * (cardW / aspect) * 1.25;
          }
          y += bob(frame, L.u * 0.8, 150, seed(seedBase + i) * 6);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                width: w,
                marginLeft: -w / 2,
                marginTop: -w / aspect / 2,
                opacity: k,
                transform: `translate3d(${x}px, ${y + (1 - k) * L.u * 6}px, ${z}px) rotateY(${rot}deg) scale(${0.9 + 0.1 * k})`,
                zIndex: Math.round(z + 1000),
              }}
            >
              <GlassCard radius={L.u * 1.2} style={{ height: w / aspect }}>
                {it.media ? (
                  <Img
                    src={asset(it.media)}
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "cover",
                      objectPosition: "top",
                    }}
                  />
                ) : (
                  <div
                    style={{
                      height: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: L.u * 2,
                      boxSizing: "border-box",
                      textAlign: "center",
                      fontFamily: FONT_SANS,
                      fontWeight: 600,
                      fontSize: fitSize(
                        it.label ?? "",
                        L.u * 2.6,
                        cardW * 0.8,
                        2,
                      ),
                      color: s.ink,
                    }}
                  >
                    {it.label}
                  </div>
                )}
              </GlassCard>
              {it.media && it.label ? (
                <div
                  style={{
                    marginTop: L.u,
                    fontFamily: FONT_MONO,
                    fontSize: L.u * 1.4,
                    color: s.inkSoft,
                    textAlign: "center",
                  }}
                >
                  {it.label}
                </div>
              ) : null}
            </div>
          );
        })}
      </AbsoluteFill>
      {p.title ? (
        <div
          style={{
            position: "absolute",
            bottom: L.safeY * 0.8,
            width: "100%",
            textAlign: "center",
            fontFamily: FONT_SANS,
            fontWeight: 600,
            fontSize: fitSize(p.title, L.u * 3.4, L.contentW, 1),
            color: s.ink,
            opacity: sEnter({ frame, fps, delay: 12 }),
          }}
        >
          {p.title}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
