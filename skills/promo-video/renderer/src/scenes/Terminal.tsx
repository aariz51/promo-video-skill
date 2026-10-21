import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sEnter } from "../animations/springs";
import { CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type Line = { type?: "cmd" | "out" | "ok" | "dim"; text: string };
type P = {
  lines: (Line | string)[];
  title?: string;
  prompt?: string;
  caption?: string;
  _t: { lines: { type: string; at: number; typeFor?: number }[] };
};

// Real commands and real output: typed at a human pace, output arriving line by line.
export const Terminal: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const lines: Line[] = p.lines.map((l) =>
    typeof l === "string" ? { type: "out", text: l } : l,
  );
  const winW = L.wide ? L.width * 0.66 : L.width * 0.9;
  const longest = lines.reduce((a, b) => Math.max(a, b.text.length + 2), 24);
  const fs = Math.min(L.u * 2.3, (winW * 0.9) / (longest * 0.62));
  const enter = sEnter({ frame, fps });
  const push = interpolate(frame, [0, scene.durationInFrames], [1, 1.05], {
    easing: EASE.inOut,
  });
  const prompt = p.prompt ?? "$";
  const bar = L.u * 3.6;
  return (
    <AbsoluteFill>
      <Ground glow={0.4} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
          gap: L.u * 4,
        }}
      >
        <div
          style={{
            width: winW,
            borderRadius: L.u * 1.4,
            overflow: "hidden",
            background: s.dark ? "#0E0F12" : "#16171A",
            border: `1.5px solid ${alpha("#ffffff", 0.08)}`,
            boxShadow: `0 60px 140px rgba(0,0,0,0.5), 0 0 80px ${alpha(s.accent, 0.08)}`,
            opacity: enter,
            transform: `translateY(${(1 - enter) * L.u * 4}px) scale(${push})`,
          }}
        >
          <div
            style={{
              height: bar,
              display: "flex",
              alignItems: "center",
              gap: bar * 0.22,
              padding: `0 ${bar * 0.45}px`,
              background: "#1A1B20",
            }}
          >
            {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
              <div
                key={c}
                style={{
                  width: bar * 0.28,
                  height: bar * 0.28,
                  borderRadius: "50%",
                  background: c,
                  opacity: 0.85,
                }}
              />
            ))}
            <div
              style={{
                flex: 1,
                textAlign: "center",
                fontFamily: FONT_MONO,
                fontSize: bar * 0.34,
                color: "#8A8D96",
                marginRight: bar,
              }}
            >
              {p.title ?? ""}
            </div>
          </div>
          <div
            style={{
              padding: `${L.u * 2.4}px ${L.u * 3}px ${L.u * 3}px`,
              fontFamily: FONT_MONO,
              fontSize: fs,
              lineHeight: 1.6,
              minHeight: L.u * 20,
            }}
          >
            {lines.map((ln, i) => {
              const sch = p._t.lines[i];
              const at = f(sch.at, fps);
              if (frame < at) return null;
              if (ln.type === "cmd") {
                const dur = Math.max(1, f(sch.typeFor ?? 0.6, fps));
                const n = Math.round(
                  interpolate(frame, [at, at + dur], [0, ln.text.length], {
                    extrapolateRight: "clamp",
                  }),
                );
                const typing = frame < at + dur + 6;
                const caret = typing && Math.floor(frame / 8) % 2 === 0;
                return (
                  <div key={i} style={{ color: "#F4F1EA", whiteSpace: "pre" }}>
                    <span style={{ color: s.accent }}>{prompt} </span>
                    {ln.text.slice(0, n)}
                    <span
                      style={{
                        opacity: caret ? 1 : 0,
                        background: "#F4F1EA",
                        marginLeft: 2,
                      }}
                    >
                      &nbsp;
                    </span>
                  </div>
                );
              }
              const k = interpolate(frame, [at, at + 6], [0, 1], {
                extrapolateRight: "clamp",
              });
              const color =
                ln.type === "ok"
                  ? s.accent
                  : ln.type === "dim"
                    ? "#6C6F78"
                    : "#C9CBD1";
              return (
                <div
                  key={i}
                  style={{
                    color,
                    opacity: k,
                    whiteSpace: "pre",
                    transform: `translateY(${(1 - k) * 6}px)`,
                  }}
                >
                  {ln.type === "ok" ? "✓ " : ""}
                  {ln.text}
                </div>
              );
            })}
          </div>
        </div>
        {p.caption ? (
          <CubeRise at={f(0.8, fps)}>
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
