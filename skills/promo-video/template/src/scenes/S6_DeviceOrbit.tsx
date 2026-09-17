import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, screens, dur } from "../theme";
import { PhoneFrame } from "../components/PhoneFrame";
import { Particles } from "../components/Particles";
import { sEnter } from "../animations/springs";
import { tailFade, pushIn } from "../animations/motion";
import { EASE } from "../animations/easings";

// Real app screens ride the ring — the breadth of the product, in motion.
// Pick six screens that SELL: skip empty-states and any screen whose numbers
// would contradict the copy on top of it.
const RING = [
  screens.detail,
  screens.search,
  screens.library,
  screens.profile,
  screens.settings,
  screens.result,
];

// Scene 6 — Device orbit. Real app screens orbit in a 3D ring around the promise
// headline "Everything built around you." Portrait: tall ring, headline up top.
// Landscape: wide ring, headline centred.
export const S6_DeviceOrbit: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;
  const opacity = tailFade(frame, dur.orbit, 16);

  const cx = width / 2;
  const cy = wide ? height / 2 : height * 0.63;
  // caps keep the ring inside narrower/shorter frames (e.g. 886px App Preview)
  const rx = wide ? Math.min(640, width * 0.34) : Math.min(340, width * 0.34);
  const ry = wide ? Math.min(250, height * 0.28) : 430;
  const orbit = frame * 0.0045; // slow rotation
  const push = pushIn(frame, 0, dur.orbit, 0.92, 1.05);

  const title = sEnter({ frame, fps, delay: 18 });

  const phones = RING.map((src, i) => {
    const base = (i / RING.length) * Math.PI * 2;
    const a = base + orbit;
    const x = Math.cos(a) * rx;
    const y = Math.sin(a) * ry;
    const depth = (Math.sin(a) + 1) / 2; // 0 back .. 1 front
    const scale = 0.6 + depth * 0.52;
    const rotY = -Math.cos(a) * 20;
    const enter = sEnter({ frame, fps, delay: 2 + i * 4 });
    return { src, x, y, scale, rotY, depth, enter, i };
  }).sort((p, q) => p.depth - q.depth);

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity, overflow: "hidden" }}>
      <Particles count={22} opacity={0.6} />

      <AbsoluteFill style={{ transform: `scale(${push})` }}>
        {phones.map((p) => {
          const ex = interpolate(p.enter, [0, 1], [0, p.x]);
          const ey = interpolate(p.enter, [0, 1], [0, p.y]);
          const es = interpolate(p.enter, [0, 1], [0.2, p.scale]);
          return (
            <div
              key={p.i}
              style={{
                position: "absolute",
                left: cx + ex,
                top: cy + ey,
                transform: `translate(-50%, -50%) perspective(1600px) rotateY(${p.rotY}deg) scale(${es})`,
                opacity: interpolate(p.enter, [0, 0.5], [0, 1]) * (0.45 + p.depth * 0.55),
                zIndex: Math.round(p.depth * 100),
                filter: `brightness(${0.82 + p.depth * 0.22})`,
              }}
            >
              <PhoneFrame src={p.src} width={230} glow="rgba(122,31,162,0.26)" />
            </div>
          );
        })}
      </AbsoluteFill>

      {/* headline on a soft cream backing glow — top (portrait) or centre (wide) */}
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: wide ? "center" : "flex-start",
          paddingTop: wide ? 0 : height * 0.16,
          zIndex: 200,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: wide ? "50%" : height * 0.09,
            transform: wide ? "translateY(-50%)" : "none",
            width: wide ? 1000 : 900,
            height: wide ? 380 : 460,
            borderRadius: "50%",
            background:
              "radial-gradient(ellipse at center, rgba(253,248,245,0.94) 0%, rgba(253,248,245,0.66) 45%, rgba(253,248,245,0) 72%)",
            opacity: title,
          }}
        />
        <div
          style={{
            fontFamily: FONT_HEAD,
            fontWeight: 800,
            fontSize: wide ? 92 : 96,
            letterSpacing: -2,
            color: COLORS.ink,
            textAlign: "center",
            lineHeight: 1.02,
            opacity: title,
            transform: `scale(${interpolate(title, [0, 1], [0.82, 1], { easing: EASE.out })})`,
            textShadow: "0 8px 40px rgba(253,248,245,0.95)",
          }}
        >
          <span style={{ color: COLORS.purple }}>Everything</span>
          <br />
          built around you.
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
