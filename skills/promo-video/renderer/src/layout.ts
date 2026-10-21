import { useVideoConfig } from "remotion";

// Layout abstraction. Scenes never use raw pixels: they size everything in `u`
// (1% of the frame's short side) and branch on `aspect`, so one scene implementation
// serves 16:9, 9:16 and 1:1 with no per-aspect animation code.
export type Aspect = "landscape" | "portrait" | "square";

export type Layout = {
  width: number;
  height: number;
  aspect: Aspect;
  u: number; // 1% of the short side
  safeX: number; // horizontal safe margin, px
  safeY: number; // vertical safe margin, px
  contentW: number;
  contentH: number;
  /** true when content should be laid out side by side */
  wide: boolean;
};

export const useLayout = (): Layout => {
  const { width, height } = useVideoConfig();
  const ratio = width / height;
  const aspect: Aspect =
    ratio > 1.15 ? "landscape" : ratio < 0.87 ? "portrait" : "square";
  const u = Math.min(width, height) / 100;
  const safeX = aspect === "landscape" ? width * 0.08 : width * 0.07;
  const safeY = aspect === "portrait" ? height * 0.09 : height * 0.1;
  return {
    width,
    height,
    aspect,
    u,
    safeX,
    safeY,
    contentW: width - safeX * 2,
    contentH: height - safeY * 2,
    wide: aspect === "landscape",
  };
};

/**
 * Largest font size (px) at which `text` fits `maxLines` lines of `boxW` px, never above
 * `base`. Character-count estimate with a conservative average glyph width, so it is
 * deterministic and needs no DOM measurement.
 */
export const fitSize = (
  text: string,
  base: number,
  boxW: number,
  maxLines = 2,
  charW = 0.56,
): number => {
  const words = text.split(/\s+/).filter(Boolean);
  let size = base;
  for (let i = 0; i < 40; i++) {
    const cap = boxW / (size * charW); // characters per line
    let lines = 1;
    let used = 0;
    for (const w of words) {
      const len = w.length + (used ? 1 : 0);
      if (used + len > cap && used > 0) {
        lines++;
        used = w.length;
      } else {
        used += len;
      }
      if (w.length > cap) lines += Math.floor(w.length / cap);
    }
    if (lines <= maxLines) return size;
    size *= 0.92;
  }
  return size;
};

/** Seconds (scene-relative, from `_t`) → frames. */
export const f = (seconds: unknown, fps: number): number =>
  Math.round(Number(seconds ?? 0) * fps);
