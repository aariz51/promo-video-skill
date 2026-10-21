import { staticFile } from "remotion";

// Bundled faces, so a render looks the same on every machine.
export const FONT_SANS = 'InterVar, "Inter", system-ui, "Segoe UI", sans-serif';
export const FONT_MONO =
  '"JetBrains Mono", ui-monospace, Menlo, Consolas, monospace';

export const FONT_FACE_CSS = `
@font-face {
  font-family: 'InterVar';
  src: url('${staticFile("fonts/Inter.ttf")}') format('truetype');
  font-weight: 100 900;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: 'JetBrains Mono';
  src: url('${staticFile("fonts/JetBrainsMono.ttf")}') format('truetype');
  font-weight: 100 800;
  font-style: normal;
  font-display: block;
}
`;
