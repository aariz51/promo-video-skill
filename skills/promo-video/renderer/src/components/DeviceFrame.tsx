import React, { useState } from "react";
import { Img, OffthreadVideo } from "remotion";
import { FONT_MONO } from "../fonts";
import { alpha, asset, isVideo, useStyle } from "../style";

export type Device = "browser" | "phone" | "desktop" | "none";

// Real product media (image or video) inside a device. Width-driven; the media's own
// aspect sets the height. A missing file renders a labelled slate instead of failing the
// render, and `promo compile` / QA report it, so the gap is visible and never silent.
export const DeviceFrame: React.FC<{
  media: string;
  device: Device;
  width: number;
  aspect: number; // media width / height
  label?: string;
  startFrom?: number; // video start, frames
}> = ({ media, device, width, aspect, label, startFrom = 0 }) => {
  const s = useStyle();
  const [failed, setFailed] = useState(false);
  const bar = device === "browser" ? Math.max(22, width * 0.03) : 0;
  const pad =
    device === "phone"
      ? width * 0.035
      : device === "desktop"
        ? width * 0.012
        : 0;
  const screenW = width - pad * 2;
  const screenH = screenW / aspect;
  const radius =
    device === "phone"
      ? width * 0.13
      : device === "none"
        ? width * 0.012
        : width * 0.014;

  const content = failed ? (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: `repeating-linear-gradient(45deg, ${s.ground2} 0 18px, ${s.ground} 18px 36px)`,
        color: s.inkSoft,
        fontFamily: FONT_MONO,
        fontSize: screenW * 0.025,
      }}
    >
      missing: {media}
    </div>
  ) : isVideo(media) ? (
    <OffthreadVideo
      src={asset(media)}
      muted
      startFrom={startFrom}
      style={{ width: "100%", height: "100%", objectFit: "cover" }}
    />
  ) : (
    <Img
      src={asset(media)}
      onError={() => setFailed(true)}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        objectPosition: "top",
      }}
    />
  );

  return (
    <div
      style={{
        width,
        borderRadius: radius,
        padding: pad,
        boxSizing: "border-box",
        background:
          device === "phone" || device === "desktop"
            ? "linear-gradient(160deg, #2A2C33, #121317)"
            : "transparent",
        boxShadow: `0 50px 120px rgba(0,0,0,${s.dark ? 0.55 : 0.2}), 0 0 0 1.5px ${alpha(s.ink, 0.1)}`,
        overflow: "hidden",
      }}
    >
      {device === "browser" ? (
        <div
          style={{
            height: bar,
            background: s.dark ? "#1B1D22" : "#E9E6DF",
            display: "flex",
            alignItems: "center",
            gap: bar * 0.3,
            padding: `0 ${bar * 0.6}px`,
          }}
        >
          {["#FF5F57", "#FEBC2E", "#28C840"].map((c) => (
            <div
              key={c}
              style={{
                width: bar * 0.36,
                height: bar * 0.36,
                borderRadius: "50%",
                background: c,
                opacity: 0.85,
              }}
            />
          ))}
          {label ? (
            <div
              style={{
                marginLeft: bar * 0.6,
                flex: 1,
                maxWidth: "55%",
                height: bar * 0.62,
                borderRadius: bar,
                background: alpha(s.ink, 0.06),
                color: s.inkSoft,
                fontFamily: FONT_MONO,
                fontSize: bar * 0.4,
                display: "flex",
                alignItems: "center",
                paddingLeft: bar * 0.5,
              }}
            >
              {label}
            </div>
          ) : null}
        </div>
      ) : null}
      <div
        style={{
          width: screenW,
          height: screenH,
          borderRadius: device === "phone" ? radius - pad : 0,
          overflow: "hidden",
          background: s.ground2,
        }}
      >
        {content}
      </div>
    </div>
  );
};
