import React from "react";
import { Composition } from "remotion";
import { Film } from "./Film";
import { WIDTH, HEIGHT, FPS, DURATION } from "./theme";

// One film, four deliverables. Every scene is orientation-aware (`width > height`)
// so all four share the same code, timing, and audio master.
export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 9:16 vertical — Reels / TikTok / Shorts / Stories (also the theme default) */}
      <Composition
        id="PromoVertical"
        component={Film}
        durationInFrames={DURATION}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
      />
      {/* 16:9 landscape — YouTube / website hero / landing */}
      <Composition
        id="PromoLandscape"
        component={Film}
        durationInFrames={DURATION}
        fps={FPS}
        width={1920}
        height={1080}
      />
      {/* App Store iPhone 6.5" App Preview — exact 886×1920 (19.5:9 portrait) */}
      <Composition
        id="PromoStorePortrait"
        component={Film}
        durationInFrames={DURATION}
        fps={FPS}
        width={886}
        height={1920}
      />
      {/* App Store App Preview — exact 1920×886 (landscape) */}
      <Composition
        id="PromoStoreLandscape"
        component={Film}
        durationInFrames={DURATION}
        fps={FPS}
        width={1920}
        height={886}
      />
    </>
  );
};
