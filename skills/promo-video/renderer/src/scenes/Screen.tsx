import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EASE } from "../animations/easings";
import { sEnter, sPop } from "../animations/springs";
import { CubeRise } from "../animations/cube";
import { Ground } from "../components/Atmosphere";
import { Cursor } from "../components/Cursor";
import { DeviceFrame, type Device } from "../components/DeviceFrame";
import { GlassCard } from "../components/GlassCard";
import { FONT_SANS } from "../fonts";
import { f, fitSize, useLayout } from "../layout";
import { alpha, useStyle } from "../style";
import type { Scene } from "../types";

type Callout = { x: number; y: number; label: string };
type P = {
  media: string;
  device?: Device;
  camera?: "push" | "pan" | "hold" | "pull" | "rise";
  focus?: { x: number; y: number };
  callouts?: Callout[];
  caption?: string;
  title?: string;
  url?: string;
  cursor?: { x: number; y: number; at?: number };
  _media?: Record<string, number>;
  _t: { callouts: number[]; click?: number };
};

// The real product, framed and directed: a device, a camera move with intent, and
// callouts that point at the thing that matters. Never a bare screenshot.
export const Screen: React.FC<{ scene: Scene }> = ({ scene }) => {
  const p = scene.props as unknown as P;
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = useLayout();
  const s = useStyle();
  const d = scene.durationInFrames;
  const device = p.device ?? "browser";
  const aspect = p._media?.[p.media] ?? 16 / 10;
  const focus = p.focus ?? { x: 0.5, y: 0.4 };
  const topRoom = p.title ? L.u * 8 : 0;
  const bottomRoom = p.caption ? L.u * 9 : 0;
  const availH = L.height - L.safeY * 1.4 - topRoom - bottomRoom;
  const maxW =
    device === "phone"
      ? L.wide
        ? L.width * 0.3
        : L.width * 0.62
      : L.wide
        ? L.width * 0.74
        : L.width * 0.9;
  const barH = device === "browser" ? Math.max(22, maxW * 0.03) : 0;
  const width = Math.min(maxW, (availH - barH) * aspect);
  const e = interpolate(frame, [0, d], [0, 1], { easing: EASE.inOut });
  const enter = sEnter({ frame, fps, delay: 0 });
  const cam = p.camera ?? "push";
  let scale = 1;
  let tx = 0;
  let ty = 0;
  let rot = 0;
  if (cam === "push") {
    scale = 1 + 0.14 * e;
    tx = (0.5 - focus.x) * width * 0.14 * e;
    ty = (0.5 - focus.y) * width * 0.08 * e;
  } else if (cam === "pull") {
    scale = 1.16 - 0.16 * e;
  } else if (cam === "pan") {
    tx = interpolate(e, [0, 1], [width * 0.05, -width * 0.05]);
    scale = 1.05;
  } else if (cam === "rise") {
    rot = interpolate(enter, [0, 1], [22, 0]);
    ty = interpolate(enter, [0, 1], [L.u * 10, 0]);
  }
  const cursorK = p.cursor
    ? interpolate(
        frame,
        [f((p._t.click ?? 1) - 0.9, fps), f(p._t.click ?? 1, fps)],
        [0, 1],
        {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: EASE.out,
        },
      )
    : 0;
  const pressed = p.cursor
    ? interpolate(
        frame,
        [
          f(p._t.click ?? 1, fps),
          f(p._t.click ?? 1, fps) + 4,
          f(p._t.click ?? 1, fps) + 10,
        ],
        [0, 1, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      )
    : 0;
  const mediaH = width / aspect + barH;

  return (
    <AbsoluteFill>
      <Ground glow={0.55} y={0.5} />
      {p.title ? (
        <CubeRise
          at={4}
          style={{
            position: "absolute",
            top: L.safeY * 0.7,
            width: "100%",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontFamily: FONT_SANS,
              fontWeight: 650,
              fontSize: fitSize(p.title, L.u * 3.6, L.contentW, 1),
              color: s.ink,
              letterSpacing: -L.u * 0.05,
            }}
          >
            {p.title}
          </div>
        </CubeRise>
      ) : null}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          paddingTop: topRoom - bottomRoom,
          perspective: 1600,
        }}
      >
        <div
          style={{
            position: "relative",
            opacity: enter,
            transform: `translate(${tx}px, ${ty}px) scale(${scale * (0.96 + 0.04 * enter)}) rotateX(${rot}deg)`,
            transformOrigin: `${focus.x * 100}% ${focus.y * 100}%`,
          }}
        >
          <DeviceFrame
            media={p.media}
            device={device}
            width={width}
            aspect={aspect}
            label={p.url}
          />
          {(p.callouts ?? []).map((c, i) => {
            const k = sPop({ frame, fps, delay: f(p._t.callouts[i], fps) });
            const left = c.x * width;
            const top = barH + c.y * (mediaH - barH);
            const toRight = c.x < 0.62;
            return (
              <div
                key={i}
                style={{ position: "absolute", left, top, opacity: k }}
              >
                <div
                  style={{
                    position: "absolute",
                    width: L.u * 1.6,
                    height: L.u * 1.6,
                    marginLeft: -L.u * 0.8,
                    marginTop: -L.u * 0.8,
                    borderRadius: "50%",
                    background: s.accent,
                    boxShadow: `0 0 0 ${L.u * 0.8 * k}px ${alpha(s.accent, 0.25)}`,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    top: -1,
                    left: toRight ? L.u * 1.2 : undefined,
                    right: toRight ? undefined : L.u * 1.2,
                    width: L.u * 5 * k,
                    height: 2,
                    background: alpha(s.accent, 0.8),
                  }}
                />
                <GlassCard
                  radius={L.u * 1}
                  active={1}
                  style={{
                    position: "absolute",
                    top: -L.u * 2.2,
                    left: toRight ? L.u * 6.4 : undefined,
                    right: toRight ? undefined : L.u * 6.4,
                    padding: `${L.u * 1}px ${L.u * 1.6}px`,
                    whiteSpace: "nowrap",
                    transform: `translateX(${(1 - k) * (toRight ? -1 : 1) * L.u * 2}px)`,
                    background: alpha(s.ground, 0.82),
                  }}
                >
                  <span
                    style={{
                      fontFamily: FONT_SANS,
                      fontWeight: 600,
                      fontSize: L.u * 2,
                      color: s.ink,
                    }}
                  >
                    {c.label}
                  </span>
                </GlassCard>
              </div>
            );
          })}
          {p.cursor ? (
            <Cursor
              x={interpolate(
                cursorK,
                [0, 1],
                [width * 1.05, p.cursor.x * width],
              )}
              y={interpolate(
                cursorK,
                [0, 1],
                [mediaH * 1.1, barH + p.cursor.y * (mediaH - barH)],
              )}
              scale={L.u / 12}
              pressed={pressed}
            />
          ) : null}
        </div>
      </AbsoluteFill>
      {p.caption ? (
        <CubeRise
          at={f(0.6, fps)}
          style={{
            position: "absolute",
            bottom: L.safeY * 0.75,
            width: "100%",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontFamily: FONT_SANS,
              fontSize: fitSize(p.caption, L.u * 3.2, L.contentW, 2),
              color: s.ink,
              fontWeight: 550,
              padding: `0 ${L.safeX}px`,
            }}
          >
            {p.caption}
          </div>
        </CubeRise>
      ) : null}
    </AbsoluteFill>
  );
};
