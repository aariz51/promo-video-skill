import React from "react";
import { AbsoluteFill } from "remotion";
import { alpha, useStyle } from "../style";
import { Particles } from "./Particles";

// The ground every scene sits on: a soft radial pool of light, grain and a vignette.
// `glow` lifts the pool (0..1); `x`/`y` move it (0..1 of the frame).
export const Ground: React.FC<{ glow?: number; x?: number; y?: number }> = ({
  glow = 0.5,
  x = 0.5,
  y = 0.45,
}) => {
  const s = useStyle();
  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 70% 60% at ${x * 100}% ${y * 100}%, ${alpha(s.accent, 0.1 * glow)} 0%, ${s.ground2} ${
            35 + 10 * glow
          }%, ${s.ground} 100%)`,
        }}
      />
      <Particles count={18} opacity={0.5} />
    </AbsoluteFill>
  );
};

// Static film grain (SVG turbulence with a fixed seed) and a vignette, over everything.
export const Finish: React.FC = () => {
  const s = useStyle();
  const noise = encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0.55 0"/></filter><rect width="100%" height="100%" filter="url(#n)"/></svg>`,
  );
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          backgroundImage: `url("data:image/svg+xml,${noise}")`,
          opacity: s.dark ? 0.07 : 0.05,
          mixBlendMode: s.dark ? "screen" : "multiply",
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse 85% 80% at 50% 50%, rgba(0,0,0,0) 55%, rgba(0,0,0,${s.dark ? 0.5 : 0.1}) 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};

// A point of light: the hook's opening image and the lockup's return.
export const PointOfLight: React.FC<{
  size: number;
  intensity: number;
  x?: number;
  y?: number;
}> = ({ size, intensity, x = 50, y = 50 }) => {
  const s = useStyle();
  if (intensity <= 0.001) return null;
  return (
    <div
      style={{
        position: "absolute",
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        marginLeft: -size / 2,
        marginTop: -size / 2,
        borderRadius: "50%",
        background: `radial-gradient(circle, #ffffff 0%, ${alpha(s.accent, 0.9)} 9%, ${alpha(s.accent, 0.25)} 28%, rgba(0,0,0,0) 68%)`,
        opacity: intensity,
        filter: "blur(0.5px)",
      }}
    />
  );
};
