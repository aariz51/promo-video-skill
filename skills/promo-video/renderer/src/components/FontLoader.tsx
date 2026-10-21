import React, { useEffect, useState } from "react";
import { delayRender, continueRender, staticFile } from "remotion";
import { FONT_FACE_CSS } from "../fonts";
import { useStyle } from "../style";

// Render-safe font loading: inject @font-face CSS, request the faces, and hold
// the render (delayRender) until document.fonts.ready resolves. delayRender is
// called inside the component (once, via useState) — never at module scope.
export const FontLoader: React.FC = () => {
  const [handle] = useState(() => delayRender("Loading film fonts"));
  const { fontFile } = useStyle();
  const productFace = fontFile
    ? `@font-face { font-family: 'ProductSans'; src: url('${staticFile(fontFile)}'); font-weight: 100 900; font-style: normal; font-display: block; }`
    : "";

  useEffect(() => {
    let cancelled = false;
    // Kick off loading of the weights we actually use.
    const loads = [
      document.fonts.load("400 40px InterVar"),
      document.fonts.load("500 40px InterVar"),
      document.fonts.load("600 40px InterVar"),
      document.fonts.load("700 40px InterVar"),
      document.fonts.load('400 40px "JetBrains Mono"'),
      document.fonts.load('600 40px "JetBrains Mono"'),
      ...(fontFile
        ? [
            document.fonts.load("400 40px ProductSans"),
            document.fonts.load("700 40px ProductSans"),
          ]
        : []),
    ];
    Promise.all(loads)
      .then(() => document.fonts.ready)
      .then(() => {
        if (!cancelled) continueRender(handle);
      })
      .catch(() => {
        if (!cancelled) continueRender(handle); // never hang on a font error
      });
    return () => {
      cancelled = true;
    };
  }, [handle, fontFile]);

  return <style>{FONT_FACE_CSS + productFace}</style>;
};
