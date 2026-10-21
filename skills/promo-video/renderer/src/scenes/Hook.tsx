import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { seed } from "../animations/motion";
import { Ground, PointOfLight } from "../components/Atmosphere";
import { KineticWords } from "../components/KineticWords";
import { FONT_MONO } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  line: string;
  eyebrow?: string;
  fragments?: string[];
  accent?: string[];
  _t: { freeze: number; line: number };
};

// Visual mystery before the product is named: a point of light; fragments of the
// viewer's world (real words from the product's domain) gather and orbit faster and
// faster; everything freezes on a beat; one line lands.
export const Hook: React.FC<{ scene: Scene; seedBase: number }> = ({
  scene,
  seedBase,
}) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const freeze = f(p._t.freeze, fps);
  const lineAt = f(p._t.line, fps);
  const frags = p.fragments ?? [];
  const tt = Math.min(frame, freeze) / fps;
  const T = Math.max(0.1, freeze / fps);
  // Angular travel: speed ramps quadratically until the freeze, then holds still.
  const travel = 0.25 * tt + (1.9 * (tt * tt * tt)) / (3 * T * T);
  const frozen = frame >= freeze;
  const light = interpolate(frame, [0, fps * 1.2], [0, 1], {
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const gather = interpolate(frame, [fps * 0.5, fps * 2.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const flash = interpolate(
    frame,
    [freeze, freeze + 3, freeze + 14],
    [0, 0.55, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const dim = frozen
    ? interpolate(frame, [freeze, freeze + 12], [1, 0.16], {
        extrapolateRight: "clamp",
      })
    : 1;
  const push = interpolate(frame, [0, scene.durationInFrames], [1, 1.06]);
  const rx = L.width * (L.wide ? 0.36 : 0.4);
  const ry = L.height * (L.wide ? 0.3 : 0.26);
  const size = fitSize(
    p.line,
    L.u * (L.wide ? 6.4 : 7.2),
    L.contentW * 0.92,
    2,
  );

  return (
    <AbsoluteFill>
      <Ground glow={0.3 + 0.5 * light} />
      <AbsoluteFill style={{ transform: `scale(${push})` }}>
        <PointOfLight
          size={L.u * (26 + 10 * Math.sin(frame / 25))}
          intensity={light * (frozen ? 0.55 : 1)}
          y={frozen ? 42 : 50}
        />
        {frags.map((text, i) => {
          // Authored placement: even angular spacing on three orbit rings, with a seeded
          // nudge so the cloud reads as organic but never collides.
          const r1 = seed(seedBase * 31 + i);
          const r2 = seed(seedBase * 31 + i + 50);
          const ring = i % 3;
          const orbit = 0.55 + ring * 0.2 + r1 * 0.06;
          const base =
            (i / Math.max(1, frags.length)) * Math.PI * 2 + ring * 0.35;
          const angle =
            base +
            r2 * 0.18 +
            travel * (0.7 + ring * 0.25) * (ring === 1 ? -1 : 1) * 2.2;
          const x = L.width / 2 + Math.cos(angle) * rx * orbit * gather;
          const y = L.height / 2 + Math.sin(angle) * ry * orbit * gather;
          const blur = frozen ? 0 : Math.min(6, travel * 1.4 * r1);
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: x,
                top: y,
                transform: "translate(-50%, -50%)",
                fontFamily: FONT_MONO,
                fontSize: L.u * (1.5 + r1 * 0.9),
                color: i % 5 === 0 ? s.accent : s.ink,
                opacity: gather * dim * (0.45 + 0.5 * r2),
                filter: `blur(${blur}px)`,
                whiteSpace: "nowrap",
                padding: `${L.u * 0.4}px ${L.u * 0.9}px`,
                border: `1px solid ${alpha(s.ink, 0.12)}`,
                borderRadius: L.u * 0.6,
                background: alpha(s.ground2, 0.6),
              }}
            >
              {text}
            </div>
          );
        })}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          background: "#ffffff",
          opacity: flash,
          mixBlendMode: s.dark ? "screen" : "normal",
        }}
      />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: `0 ${L.safeX}px`,
          paddingTop: L.height * 0.2,
        }}
      >
        {frame >= lineAt - 1 ? (
          <div style={{ textAlign: "center" }}>
            {p.eyebrow ? (
              <div
                style={{
                  fontFamily: FONT_MONO,
                  fontSize: L.u * 1.6,
                  color: s.accent,
                  letterSpacing: L.u * 0.3,
                  marginBottom: L.u * 2,
                  textTransform: "uppercase",
                  opacity: interpolate(frame, [lineAt, lineAt + 12], [0, 1], {
                    extrapolateRight: "clamp",
                  }),
                }}
              >
                {p.eyebrow}
              </div>
            ) : null}
            <KineticWords
              text={p.line}
              accent={p.accent}
              fontSize={size}
              startAt={lineAt}
              stagger={5}
              maxWidth={L.contentW}
            />
          </div>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
