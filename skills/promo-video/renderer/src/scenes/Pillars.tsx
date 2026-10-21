import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { sEnter } from "../animations/springs";
import { Ground } from "../components/Atmosphere";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type Item = { title: string; detail?: string };
type P = {
  items: (Item | string)[];
  focus?: number;
  title?: string;
  _t: { items: number[]; focus: number };
};

// The shape of the product: two to four ideas or stages the eye can hold at once.
// At `focus`, one pillar stays lit and the others step back.
export const Pillars: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const items: Item[] = p.items.map((i) =>
    typeof i === "string" ? { title: i } : i,
  );
  const focusAt = f(p._t.focus, fps);
  const focusK =
    p.focus === undefined
      ? 0
      : interpolate(frame, [focusAt, focusAt + 14], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const n = items.length;
  const colW = L.wide ? L.contentW / n : L.contentW;
  const longest = items.reduce(
    (a, b) => (b.title.length > a.length ? b.title : a),
    "",
  );
  const titleSize = fitSize(
    longest,
    L.u * (L.wide ? 5.4 : 6.2),
    colW * 0.88,
    1,
    0.6,
  );
  return (
    <AbsoluteFill>
      <Ground glow={0.4} />
      <AbsoluteFill
        style={{
          padding: `${L.safeY}px ${L.safeX}px`,
          justifyContent: "center",
        }}
      >
        {p.title ? (
          <div
            style={{
              fontFamily: FONT_MONO,
              fontSize: L.u * 1.8,
              color: s.inkSoft,
              letterSpacing: L.u * 0.3,
              textTransform: "uppercase",
              textAlign: "center",
              marginBottom: L.u * 6,
              opacity: sEnter({ frame, fps, delay: 0 }),
            }}
          >
            {p.title}
          </div>
        ) : null}
        <div
          style={{
            display: "flex",
            flexDirection: L.wide ? "row" : "column",
            gap: L.wide ? 0 : L.u * 5,
          }}
        >
          {items.map((it, i) => {
            const k = sEnter({ frame, fps, delay: f(p._t.items[i], fps) });
            const isFocus = p.focus === i;
            const dimTo = isFocus ? 1 : 1 - 0.65 * focusK;
            return (
              <div
                key={i}
                style={{
                  width: colW,
                  textAlign: "center",
                  opacity: k * dimTo,
                  transform: `translateY(${(1 - k) * L.u * 4}px) scale(${1 + (isFocus ? 0.06 * focusK : 0)})`,
                  borderLeft:
                    L.wide && i > 0
                      ? `1px solid ${alpha(s.ink, 0.12 * k)}`
                      : undefined,
                  padding: `0 ${L.u * 2}px`,
                  boxSizing: "border-box",
                }}
              >
                <div
                  style={{
                    fontFamily: FONT_SANS,
                    fontWeight: 700,
                    fontSize: titleSize,
                    letterSpacing: -titleSize * 0.03,
                    color: isFocus && focusK > 0.5 ? s.accent : s.ink,
                  }}
                >
                  {it.title}
                </div>
                {it.detail ? (
                  <div
                    style={{
                      fontFamily: FONT_SANS,
                      fontSize: fitSize(it.detail, L.u * 2.2, colW * 0.8, 2),
                      color: s.inkSoft,
                      marginTop: L.u * 1.6,
                      lineHeight: 1.35,
                    }}
                  >
                    {it.detail}
                  </div>
                ) : null}
                <div
                  style={{
                    height: 3,
                    width: `${30 * (isFocus ? focusK : 0)}%`,
                    margin: `${L.u * 2}px auto 0`,
                    background: s.accent,
                    borderRadius: 2,
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
