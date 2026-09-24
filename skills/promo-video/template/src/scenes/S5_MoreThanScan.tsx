import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { COLORS, BG_RADIAL, FONT_HEAD, FONT_BODY, dur } from "../theme";
import { Particles } from "../components/Particles";
import { Whoosh } from "../components/Whoosh";
import { GlassCard } from "../components/GlassCard";
import { sEnter } from "../animations/springs";
import { bob, tailFade } from "../animations/motion";
import { CubeList } from "../animations/cube";

type Feat = { label: string; sub: string; tint: string; icon: React.ReactNode; dir: number };

const Icon = {
  health: (
    <svg width="72" height="72" viewBox="0 0 24 24" fill="none">
      <path d="M3 12h4l2-5 3 10 2-5h4" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  expert: (
    <svg width="70" height="70" viewBox="0 0 24 24" fill="none">
      <path d="M12 3l1.8 4.6L18.5 9l-4.7 1.4L12 15l-1.8-4.6L5.5 9l4.7-1.4L12 3z" fill="#fff" />
      <circle cx="18.5" cy="17.5" r="2" fill="#fff" />
    </svg>
  ),
  docs: (
    <svg width="66" height="66" viewBox="0 0 24 24" fill="none">
      <path d="M7 3h7l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" stroke="#fff" strokeWidth="2" strokeLinejoin="round" />
      <path d="M14 3v4h4M9 12h6M9 16h6" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  ),
};

const FEATS: Feat[] = [
  { label: "Live Score", sub: "Tracked over time", tint: COLORS.pink, icon: Icon.health, dir: -1 },
  { label: "Ask an Expert", sub: "AI guidance, on call", tint: COLORS.purple, icon: Icon.expert, dir: 1 },
  { label: "Docs & Reports", sub: "Understand every result", tint: COLORS.gold, icon: Icon.docs, dir: -1 },
];

// Scene 5 — "More than a scanner." Three glass feature cards. Portrait: stacked
// wide rows. Landscape: a fanned row of tall cards. Whoosh stitches the section.
export const S5_MoreThanScan: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const wide = width > height;
  const opacity = tailFade(frame, dur.more, 12);

  const title = sEnter({ frame, fps, delay: 14 });

  const Title = (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: wide ? height * 0.13 : height * 0.14 }}>
      <div
        style={{
          fontFamily: FONT_HEAD,
          fontWeight: 700,
          fontSize: wide ? 92 : 82,
          letterSpacing: -1.5,
          color: COLORS.ink,
          textAlign: "center",
          lineHeight: 1.05,
          opacity: title,
          transform: `translateY(${interpolate(title, [0, 1], [40, 0])}px)`,
        }}
      >
        {wide ? (
          <>More than an <span style={{ color: COLORS.purple }}>answer.</span></>
        ) : (
          <>More than<br />an <span style={{ color: COLORS.purple }}>answer.</span></>
        )}
      </div>
    </AbsoluteFill>
  );

  return (
    <AbsoluteFill style={{ background: BG_RADIAL, opacity }}>
      <Particles count={16} opacity={0.6} />
      {Title}

      {wide ? (
        // Landscape — fanned row of tall cards
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: height * 0.1 }}>
          <div style={{ display: "flex", gap: 60 }}>
            {FEATS.map((f, i) => {
              const s = sEnter({ frame, fps, delay: 26 + i * 9 });
              const floatY = bob(frame, 12, 130, i * 1.4);
              return (
                <div
                  key={i}
                  style={{
                    transform: `translateY(${interpolate(s, [0, 1], [80, floatY])}px) rotate(${(i - 1) * 6}deg) scale(${interpolate(s, [0, 1], [0.6, 1])})`,
                    opacity: s,
                  }}
                >
                  <GlassCard width={320} height={380} tint={f.tint} glow={`${f.tint}55`}>
                    <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 26 }}>
                      {f.icon}
                      <CubeList at={40 + i * 9} itemStyle={{ textAlign: "center" }}>
                        <div style={{ fontFamily: FONT_HEAD, fontWeight: 800, fontSize: 40, color: "#fff" }}>{f.label}</div>
                        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 26, color: "rgba(255,255,255,0.9)", marginTop: 8 }}>{f.sub}</div>
                      </CubeList>
                    </div>
                  </GlassCard>
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      ) : (
        // Portrait — stacked wide rows
        <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: height * 0.12 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 40 }}>
            {FEATS.map((f, i) => {
              const s = sEnter({ frame, fps, delay: 26 + i * 9 });
              const floatY = bob(frame, 9, 140, i * 1.6);
              const floatX = interpolate(s, [0, 1], [f.dir * 120, 0]);
              return (
                <div
                  key={i}
                  style={{
                    transform: `translate(${floatX}px, ${interpolate(s, [0, 1], [40, floatY])}px) scale(${interpolate(s, [0, 1], [0.7, 1])})`,
                    opacity: s,
                  }}
                >
                  <GlassCard width={width * 0.82} height={200} tint={f.tint} glow={`${f.tint}55`} radius={40}>
                    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", gap: 40, padding: "0 46px" }}>
                      <div
                        style={{
                          width: 118, height: 118, borderRadius: 30,
                          background: "rgba(255,255,255,0.22)",
                          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                          border: "1.5px solid rgba(255,255,255,0.4)",
                        }}
                      >
                        {f.icon}
                      </div>
                      <CubeList at={40 + i * 9} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <div style={{ fontFamily: FONT_HEAD, fontWeight: 800, fontSize: 52, color: "#fff", lineHeight: 1 }}>{f.label}</div>
                        <div style={{ fontFamily: FONT_BODY, fontWeight: 500, fontSize: 30, color: "rgba(255,255,255,0.9)" }}>{f.sub}</div>
                      </CubeList>
                    </div>
                  </GlassCard>
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      )}

      <Whoosh frame={frame} start={0} span={22} />
    </AbsoluteFill>
  );
};
