import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sEnter, sSettle } from "../animations/springs";
import { Ground } from "../components/Atmosphere";
import { FONT_MONO, FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type P = {
  line: string;
  then?: string;
  word: string;
  through?: number;
  name?: string;
  tags?: [string, string];
  _t: {
    typeFor: number;
    then?: number;
    cursors: number;
    select: number;
    zoom: [number, number];
    name: number;
  };
};

const CHAR = 0.6; // JetBrains Mono advance width, in em: positions are exact

// Typographic hook: a small line types in; two cursors arrive and select one word; the
// word scales toward the camera and the camera flies through one of its letters into the
// accent ground, where the name lands.
export const WordZoom: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const t = p._t;
  const thenAt = t.then !== undefined ? f(t.then, fps) : Infinity;
  const text = frame >= thenAt ? p.then! : p.line;
  const typedChars =
    frame >= thenAt
      ? Math.round(
          interpolate(frame, [thenAt, thenAt + f(0.6, fps)], [0, text.length], {
            extrapolateRight: "clamp",
          }),
        )
      : Math.round(
          interpolate(
            frame,
            [f(0.3, fps), f(0.3 + t.typeFor, fps)],
            [0, text.length],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            },
          ),
        );
  const size = Math.min(L.u * 3, fitSize(text, L.u * 3, L.contentW, 1, CHAR));
  // The word may only exist in the final text (`then`); until it appears, the line is
  // plain text with no selectable span.
  const found = text.indexOf(p.word);
  const hasWord = found >= 0;
  const wi = hasWord ? found : text.length;
  const through = p.through ?? Math.max(0, p.word.search(/[oaeqdbpg]/i));
  // Centre of the target letter, relative to the line's centre, in px at scale 1.
  const letterX = (wi + through + 0.5 - text.length / 2) * CHAR * size;
  const [z0, z1] = [f(t.zoom[0], fps), f(t.zoom[1], fps)];
  const zp = interpolate(frame, [z0, z1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE.in,
  });
  const scale = Math.pow(90, zp);
  const sel = sEnter({ frame, fps, delay: f(t.select, fps) });
  const cur = sEnter({ frame, fps, delay: f(t.cursors, fps) });
  const others =
    1 - interpolate(zp, [0, 0.25], [0, 1], { extrapolateRight: "clamp" });
  const groundIn = interpolate(
    frame,
    [z1 - f(0.1, fps), z1 + f(0.08, fps)],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const nameK = sSettle({ frame, fps, delay: f(t.name, fps) });
  const tags = p.tags ?? ["you", "agent"];
  const before = text.slice(0, wi);
  const after = hasWord ? text.slice(wi + p.word.length) : "";
  const shown = (seg: string, start: number) =>
    seg.slice(0, Math.max(0, Math.min(seg.length, typedChars - start)));
  const caret = typedChars < text.length && Math.floor(frame / 8) % 2 === 0;

  const pointer = (color: string, label: string, dx: number, dy: number) => (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        transform: `translate(${dx * (2 - cur)}px, ${dy * (2 - cur)}px)`,
        opacity: cur * others,
      }}
    >
      <svg width={size * 0.7} height={size * 0.7} viewBox="0 0 20 20">
        <path
          d="M2 2 L18 9 L10 11 L8 18 Z"
          fill={color}
          stroke={s.ground}
          strokeWidth="1.5"
        />
      </svg>
      <span
        style={{
          fontFamily: FONT_SANS,
          fontSize: size * 0.42,
          color: "#fff",
          background: color,
          padding: `${size * 0.06}px ${size * 0.2}px`,
          borderRadius: size * 0.2,
          marginLeft: size * 0.1,
        }}
      >
        {label}
      </span>
    </div>
  );

  return (
    <AbsoluteFill>
      <Ground glow={0.2} />
      <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
        <div
          style={{
            fontFamily: FONT_MONO,
            fontSize: size,
            color: s.ink,
            whiteSpace: "pre",
            transformOrigin: `calc(50% + ${letterX}px) 50%`,
            transform: `translateX(${-letterX * zp}px) scale(${scale})`,
          }}
        >
          <span style={{ opacity: others }}>{shown(before, 0)}</span>
          {hasWord ? (
            <span
              style={{ position: "relative", color: zp > 0 ? s.accent : s.ink }}
            >
              {shown(p.word, before.length)}
              <span
                style={{
                  position: "absolute",
                  inset: `-${size * 0.18}px -${size * 0.14}px`,
                  border: `${Math.max(1.5, size * 0.06)}px solid ${s.accent}`,
                  background: alpha(s.accent, 0.08),
                  opacity: sel * others,
                  transform: `scale(${0.9 + 0.1 * sel})`,
                }}
              />
              {pointer(s.accent, tags[0], -size * 3.2, -size * 2.2)}
              {pointer(s.inkSoft, tags[1], size * 2.4, size * 1.2)}
            </span>
          ) : null}
          <span style={{ opacity: others }}>
            {shown(after, before.length + p.word.length)}
          </span>
          <span style={{ opacity: caret ? 0.8 : 0 }}>▍</span>
        </div>
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          background: s.accent,
          opacity: groundIn,
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        {p.name ? (
          <div
            style={{
              fontFamily: FONT_SANS,
              fontWeight: 700,
              fontSize: fitSize(p.name, L.u * 11, L.contentW, 1, 0.6),
              color: "#ffffff",
              letterSpacing: -L.u * 0.3,
              opacity: nameK,
              transform: `scale(${0.94 + 0.06 * nameK})`,
            }}
          >
            {p.name}
          </div>
        ) : null}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
