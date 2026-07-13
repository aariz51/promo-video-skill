import { staticFile } from "remotion";

// Warm rounded display face for headlines, numbers, brand voice.
export const FONT_HEAD = '"Baloo 2", system-ui, "Segoe UI", sans-serif';
// Clean grotesque for UI chrome, small labels, dates.
export const FONT_BODY = 'InterVar, system-ui, "Segoe UI", sans-serif';

// @font-face CSS for the bundled variable TTFs. Injected by <FontLoader/>.
export const FONT_FACE_CSS = `
@font-face {
  font-family: 'Baloo 2';
  src: url('${staticFile("fonts/Baloo2.ttf")}') format('truetype');
  font-weight: 400 800;
  font-style: normal;
  font-display: block;
}
@font-face {
  font-family: 'InterVar';
  src: url('${staticFile("fonts/Inter.ttf")}') format('truetype');
  font-weight: 100 900;
  font-style: normal;
  font-display: block;
}
`;
