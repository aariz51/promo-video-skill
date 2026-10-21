import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  value: string | number;
  label: string;
  prefix?: string;
  suffix?: string;
  small?: string;
  _t: { count: [number, number] };
};

// One sourced number, revealed big. The engine refuses this scene without a claim id.
export const Metric: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const [a, b] = p._t.count.map((t) => f(t, fps));
  const raw = String(p.value);
  const num = parseFloat(raw.replace(/,/g, ""));
  const decimals = (raw.split(".")[1] ?? "").length;
  const k = interpolate(frame, [a, b], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.out,
  });
  const shown = Number.isFinite(num)
    ? (num * k).toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })
    : raw;
  const text = `${p.prefix ?? ""}${shown}${p.suffix ?? ""}`;
  const size = fitSize(
    `${p.prefix ?? ""}${raw}${p.suffix ?? ""}`,
    L.u * 22,
    L.contentW,
    1,
    0.62,
  );
  const land = interpolate(frame, [b, b + 10], [1.04, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill>
      <Ground glow={0.3 + 0.5 * k} />
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            fontFamily: FONT_SANS,
            fontWeight: 700,
            fontSize: size,
            color: s.ink,
            letterSpacing: -size * 0.04,
            fontVariantNumeric: "tabular-nums",
            transform: `scale(${land})`,
            opacity: interpolate(frame, [a - 6, a + 4], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {text}
        </div>
        <CubeRise at={b} style={{ marginTop: L.u * 2 }}>
          <div
            style={{
              fontFamily: FONT_SANS,
              fontSize: fitSize(p.label, L.u * 3.4, L.contentW, 2),
              color: s.accent,
              fontWeight: 600,
              textAlign: "center",
            }}
          >
            {p.label}
          </div>
        </CubeRise>
        {p.small ? (
          <CubeRise
            at={b + 12}
            style={{
              position: "absolute",
              bottom: L.safeY * 0.8,
              width: "100%",
            }}
          >
            <div
              style={{
                fontFamily: FONT_SANS,
                fontSize: L.u * 1.6,
                color: s.inkSoft,
                textAlign: "center",
                padding: `0 ${L.safeX}px`,
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
