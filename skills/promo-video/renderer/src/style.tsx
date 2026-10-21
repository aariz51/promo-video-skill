import React, { createContext, useContext } from "react";
import { staticFile } from "remotion";
import type { Style } from "./types";

// The resolved style (from render-config.json) is provided once by <Film> and read by
// every scene and component. Colours never come from anywhere else.
export const DEFAULT_STYLE: Style = {
  preset: "graphite",
  ground: "#0B0C0F",
  ground2: "#16181D",
  ink: "#F4F1EA",
  inkSoft: "#9A9DA6",
  accent: "#6E9BFF",
  line: "#2A2D35",
  dark: true,
  fontHead: "Inter",
};

const Ctx = createContext<Style>(DEFAULT_STYLE);
export const StyleProvider: React.FC<{
  style: Style;
  children: React.ReactNode;
}> = ({ style, children }) => (
  <Ctx.Provider value={style}>{children}</Ctx.Provider>
);
export const useStyle = () => useContext(Ctx);

/** `#rrggbb` + alpha (0–1) → rgba() */
export const alpha = (hex: string, a: number): string => {
  const h = hex.replace("#", "");
  const n = parseInt(
    h.length === 3
      ? h
          .split("")
          .map((c) => c + c)
          .join("")
      : h,
    16,
  );
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
};

/** Product media always lives under the staged public dir's assets/ folder. */
export const asset = (ref: string) => staticFile(`assets/${ref}`);

export const isVideo = (ref: string) => /\.(mp4|mov|webm|m4v)$/i.test(ref);
