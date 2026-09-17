import React, { useEffect, useState } from "react";
import { delayRender, continueRender } from "remotion";
import { FONT_FACE_CSS } from "../fonts";

// Render-safe font loading: inject @font-face CSS, request the faces, and hold
// the render (delayRender) until document.fonts.ready resolves. delayRender is
// called inside the component (once, via useState) — never at module scope.
export const FontLoader: React.FC = () => {
  const [handle] = useState(() => delayRender("Loading film fonts"));

  useEffect(() => {
    let cancelled = false;
    // Kick off loading of the weights we actually use.
    const loads = [
      document.fonts.load('800 40px "Baloo 2"'),
      document.fonts.load('700 40px "Baloo 2"'),
      document.fonts.load('500 40px InterVar'),
      document.fonts.load('600 40px InterVar'),
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
  }, [handle]);

  return <style>{FONT_FACE_CSS}</style>;
};
