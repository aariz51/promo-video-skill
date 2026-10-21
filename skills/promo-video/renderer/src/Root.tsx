import React from "react";
import { Composition, type CalculateMetadataFunction } from "remotion";
import { Film } from "./Film";
import sample from "./sample/render-config.json";
import type { RenderConfig } from "./types";

// Five compositions, one film. Length and frame rate come from the input props
// (render-config.json), so nothing here changes per product.
const metadata: CalculateMetadataFunction<RenderConfig> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: props.fps,
});

const FORMATS = [
  { id: "Promo16x9", width: 1920, height: 1080 }, // master
  { id: "Promo9x16", width: 1080, height: 1920 },
  { id: "Promo1x1", width: 1080, height: 1080 },
  // App Store app previews at the exact device size (never a letterboxed 1080-wide file).
  { id: "PromoStorePortrait", width: 886, height: 1920 },
  { id: "PromoStoreLandscape", width: 1920, height: 886 },
] as const;

export const RemotionRoot: React.FC = () => (
  <>
    {FORMATS.map((fmt) => (
      <Composition
        key={fmt.id}
        id={fmt.id}
        component={Film}
        width={fmt.width}
        height={fmt.height}
        fps={30}
        durationInFrames={300}
        defaultProps={sample as unknown as RenderConfig}
        calculateMetadata={metadata}
      />
    ))}
  </>
);
