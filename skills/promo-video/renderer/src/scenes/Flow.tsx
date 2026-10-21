import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sEnter } from "../animations/springs";
import { CubeList } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { GlassCard } from "../components/GlassCard";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, asset, useStyle } from "../style";
import type { Scene } from "../types";

type Step = {
  label: string;
  detail?: string;
  lines?: string[];
  media?: string;
  kind?: "input" | "process" | "result";
};
type P = { steps: Step[]; title?: string; _t: { steps: number[] } };

// Show, don't tell: INPUT → PROCESS → RESULT. A pulse of light travels the connector
// and each step lights up as it arrives; the last step resolves in the accent colour.
export const Flow: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const n = p.steps.length;
  const times = p._t.steps.map((t) => f(t, fps));
  const topRoom = p.title ? L.u * 10 : 0;
  const gap = L.u * (L.wide ? 5 : 3.2);
  const cardW = L.wide ? (L.contentW - gap * (n - 1)) / n : L.contentW;
  const cardH = L.wide
    ? Math.min(L.contentH - topRoom, L.u * 46)
    : (L.contentH - topRoom - gap * (n - 1)) / n;
  const progress = interpolate(
    frame,
    times,
    times.map((_, i) => i),
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE.inOut },
  );

  return (
    <AbsoluteFill>
      <Ground glow={0.45} />
      <AbsoluteFill
        style={{
          padding: `${L.safeY}px ${L.safeX}px`,
          justifyContent: "center",
        }}
      >
        {p.title ? (
          <div
            style={{
              height: topRoom,
              fontFamily: FONT_SANS,
              fontWeight: 650,
              fontSize: fitSize(p.title, L.u * 3.8, L.contentW, 1),
              color: s.ink,
              textAlign: "center",
              opacity: sEnter({ frame, fps }),
            }}
          >
            {p.title}
          </div>
        ) : null}
        <div
          style={{
            position: "relative",
            display: "flex",
            flexDirection: L.wide ? "row" : "column",
            gap,
          }}
        >
          {p.steps.map((st, i) => {
            const k = sEnter({ frame, fps, delay: times[i] - 8 });
            const lit = interpolate(frame, [times[i], times[i] + 10], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const isResult = i === n - 1 || st.kind === "result";
            const kind =
              st.kind ?? (i === 0 ? "input" : isResult ? "result" : "process");
            // Square frames are too short for stacked cards, so each card becomes a row:
            // what the step is on the left, what it contains on the right.
            const row = L.aspect === "square";
            const textW = row ? cardW * 0.44 : cardW * 0.84;
            const labelSize = fitSize(
              st.label,
              L.u * (L.wide ? 3.3 : row ? 3.2 : 3.6),
              textW,
              2,
            );
            return (
              <GlassCard
                key={i}
                width={cardW}
                height={cardH}
                radius={L.u * 2}
                active={lit}
                fill={isResult ? lit : 0}
                style={{
                  opacity: 0.25 + 0.75 * k,
                  transform: `translateY(${(1 - k) * L.u * 3}px)`,
                  padding: row ? `${L.u * 1.6}px ${L.u * 2.6}px` : L.u * 2.6,
                  display: "flex",
                  flexDirection: row ? "row" : "column",
                  alignItems: row ? "center" : undefined,
                  gap: L.u * 1.4,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: L.u * (row ? 0.6 : 1.4),
                    width: row ? textW : undefined,
                  }}
                >
                  <div
                    style={{
                      fontFamily: FONT_MONO,
                      fontSize: L.u * 1.5,
                      letterSpacing: L.u * 0.25,
                      textTransform: "uppercase",
                      color: lit > 0.5 ? s.accent : s.inkSoft,
                    }}
                  >
                    {kind}
                  </div>
                  <div
                    style={{
                      fontFamily: FONT_SANS,
                      fontWeight: 650,
                      fontSize: labelSize,
                      color: s.ink,
                      lineHeight: 1.12,
                      letterSpacing: -labelSize * 0.02,
                    }}
                  >
                    {st.label}
                  </div>
                  {st.detail ? (
                    <div
                      style={{
                        fontFamily: FONT_SANS,
                        fontSize: fitSize(st.detail, L.u * 2, cardW * 0.84, 3),
                        color: s.inkSoft,
                        lineHeight: 1.35,
                      }}
                    >
                      {st.detail}
                    </div>
                  ) : null}
                </div>
                {st.media ? (
                  <div
                    style={{
                      flex: 1,
                      minHeight: 0,
                      borderRadius: L.u,
                      overflow: "hidden",
                      opacity: lit,
                    }}
                  >
                    <Img
                      src={asset(st.media)}
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        objectPosition: "top",
                      }}
                    />
                  </div>
                ) : null}
                {st.lines?.length ? (
                  <CubeList
                    at={times[i] + 4}
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: L.u * 0.7,
                    }}
                  >
                    {st.lines.map((ln, j) => (
                      <div
                        key={j}
                        style={{
                          fontFamily: FONT_MONO,
                          fontSize: fitSize(
                            ln,
                            L.u * 1.7,
                            row ? cardW * 0.46 : cardW * 0.86,
                            1,
                            0.62,
                          ),
                          color: s.ink,
                          opacity: 0.85,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {ln}
                      </div>
                    ))}
                  </CubeList>
                ) : null}
              </GlassCard>
            );
          })}
          {/* connectors + travelling pulse */}
          {p.steps.slice(1).map((_, i) => {
            const seg = Math.min(1, Math.max(0, progress - i));
            const style: React.CSSProperties = L.wide
              ? {
                  left: (cardW + gap) * (i + 1) - gap,
                  top: cardH / 2,
                  width: gap,
                  height: 2,
                }
              : {
                  top: (cardH + gap) * (i + 1) - gap,
                  left: L.contentW / 2,
                  height: gap,
                  width: 2,
                };
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  background: alpha(s.ink, 0.15),
                  ...style,
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    background: s.accent,
                    transformOrigin: L.wide ? "left" : "top",
                    transform: L.wide ? `scaleX(${seg})` : `scaleY(${seg})`,
                    boxShadow: `0 0 12px ${s.accent}`,
                  }}
                />
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
