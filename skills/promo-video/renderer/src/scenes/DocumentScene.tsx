import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sSettle } from "../animations/springs";
import { CubeList, CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { GlassCard } from "../components/GlassCard";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type Section = { heading: string; lines: string[] };
type P = {
  title: string;
  sections: Section[];
  caption?: string;
  source?: string;
  _t: { sections: number[] };
};

// Structured output assembling itself: a real artifact the product produces, section by
// section, settling out of a slight tilt.
export const DocumentScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const k = sSettle({ frame, fps });
  const drift = interpolate(frame, [0, scene.durationInFrames], [0, 1], {
    easing: EASE.inOut,
  });
  const docW = L.wide ? L.width * 0.62 : L.width * 0.88;
  const longest = Math.max(
    ...p.sections.flatMap((sec) => sec.lines.map((ln) => ln.length)),
  );
  // Two columns only when every line is short enough to stay large in a half-width column.
  const cols = L.wide && p.sections.length > 2 && longest <= 34 ? 2 : 1;
  const colW = (docW - L.u * 7 - (cols - 1) * L.u * 3) / cols;
  const lineSize = Math.min(
    L.u * 2.3,
    ...p.sections.flatMap((sec) =>
      sec.lines.map((ln) => fitSize(ln, L.u * 2.3, colW, 1, 0.58)),
    ),
  );
  return (
    <AbsoluteFill>
      <Ground glow={0.45} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: L.u * 3.4,
          perspective: 1800,
        }}
      >
        <GlassCard
          width={docW}
          radius={L.u * 1.6}
          style={{
            padding: L.u * 3,
            opacity: k,
            transform: `rotateX(${(1 - k) * 18 + 4 * (1 - drift)}deg) rotateY(${-6 + 4 * drift}deg) translateY(${(1 - k) * L.u * 6}px)`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              borderBottom: `1px solid ${alpha(s.ink, 0.12)}`,
              paddingBottom: L.u * 1.4,
              marginBottom: L.u * 2,
            }}
          >
            <div
              style={{
                fontFamily: FONT_SANS,
                fontWeight: 700,
                fontSize: fitSize(p.title, L.u * 3, docW * 0.7, 1),
                color: s.ink,
              }}
            >
              {p.title}
            </div>
            {p.source ? (
              <div
                style={{
                  fontFamily: FONT_MONO,
                  fontSize: L.u * 1.4,
                  color: s.inkSoft,
                }}
              >
                {p.source}
              </div>
            ) : null}
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${cols}, 1fr)`,
              columnGap: L.u * 3,
              rowGap: L.u * 2,
            }}
          >
            {p.sections.map((sec, i) => {
              const at = f(p._t.sections[i], fps);
              const on = interpolate(frame, [at, at + 8], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={i}
                  style={{
                    borderLeft: `2px solid ${alpha(s.accent, 0.2 + 0.7 * on)}`,
                    paddingLeft: L.u * 1.6,
                    opacity: 0.2 + 0.8 * on,
                  }}
                >
                  <div
                    style={{
                      fontFamily: FONT_MONO,
                      fontSize: L.u * 1.45,
                      letterSpacing: L.u * 0.2,
                      textTransform: "uppercase",
                      color: s.accent,
                      marginBottom: L.u * 0.9,
                    }}
                  >
                    {sec.heading}
                  </div>
                  <CubeList
                    at={at + 3}
                    stagger={90}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: L.u * 0.55,
                    }}
                  >
                    {sec.lines.map((ln, j) => (
                      <div
                        key={j}
                        style={{
                          fontFamily: FONT_SANS,
                          fontSize: lineSize,
                          color: s.ink,
                          opacity: 0.9,
                          whiteSpace: "pre",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {ln}
                      </div>
                    ))}
                  </CubeList>
                </div>
              );
            })}
          </div>
        </GlassCard>
        {p.caption ? (
          <CubeRise at={f(1.0, fps)}>
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: fitSize(p.caption, L.u * 3, L.contentW, 2),
                color: s.ink,
                fontWeight: 550,
                textAlign: "center",
                maxWidth: L.contentW,
              }}
            >
              {p.caption}
            </div>
          </CubeRise>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
