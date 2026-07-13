// ════════════════════════════════════════════════════════════════════════════
//  BRAND SYSTEM + FILM TIMING — the single source of truth for the whole film.
//  ► To retarget this template to a new app, this is the FIRST file to edit:
//    swap COLORS for the app's palette, point `screens`/`LOGO` at its assets,
//    and (optionally) pick fonts in ./fonts.ts. Keep `T`/`dur` unchanged so the
//    prebuilt audio stays in sync — or change them and rebuild audio to match.
//  The shipped values are the worked example (a warm pregnancy-safety scanner).
// ════════════════════════════════════════════════════════════════════════════
import { FONT_HEAD, FONT_BODY } from "./fonts";

export { FONT_HEAD, FONT_BODY };

export const COLORS = {
  // Warm base (background system)
  cream: "#FDF8F5",
  creamDeep: "#FBEFE9",
  blush: "#F7E0E6",
  // Brand primary / secondary / accent
  purple: "#7A1FA2",
  purpleSoft: "#9A44C4",
  purpleDeep: "#5E1580",
  pink: "#E84B8A",
  pinkSoft: "#F58FB6",
  gold: "#F4B400",
  goldSoft: "#FFD46B",
  // Result semantics (good / warn / bad) — recolour for your domain
  safe: "#2FB56A",
  safeSoft: "#7ED9A6",
  caution: "#FF8C00",
  avoid: "#E5484D",
  // Ink
  ink: "#2B2D42",
  inkSoft: "#6B6E86",
  white: "#FFFFFF",
} as const;

// Canvas — 9:16 vertical (App Store preview / Reels / TikTok / Shorts / Stories).
export const FPS = 60;
export const WIDTH = 1080;
export const HEIGHT = 1920;
export const DURATION = 1980; // 33s

// Native app-screen dimensions (portrait phone)
export const SCREEN_W = 1080;
export const SCREEN_H = 2340;
export const SCREEN_RATIO = SCREEN_W / SCREEN_H; // ~0.4615

export const screens = {
  dashboard: "app-screens/01-safemama-dashboard.png",
  health: "app-screens/02-pregnancy-health-score.png",
  drawer: "app-screens/03-drawer-menu.png",
  scanMode: "app-screens/04-scan-mode-selection.png",
  barcode: "app-screens/05-barcode-scan-interface.png",
  history: "app-screens/06-scan-history.png",
  result: "app-screens/07-existing-scan-result.png",
  document: "app-screens/08-document-analysis.png",
  expert: "app-screens/09-ask-expert.png",
  test: "app-screens/10-pregnancy-test.png",
  community: "app-screens/11-community.png",
  search: "app-screens/12-manual-search.png",
  tools: "app-screens/13-free-tools.png",
  calculator: "app-screens/14-pregnancy-tools-calculator.png",
  guide: "app-screens/15-ai-personalized-guide.png",
} as const;

export const LOGO = "logo/app-logo.png";

// The pre-mixed audio master (VO + SFX + pad), built by scripts/build_audio.py.
// Set to null to preview the film silently before the master exists.
export const AUDIO_SRC: string | null = "audio/master.wav";

// Scene boundaries in frames @ 60fps (start-inclusive).
export const T = {
  hook: 0, //        0.0 - 3.5
  oneTap: 210, //    3.5 - 6.0
  press: 360, //     6.0 - 8.0
  verdict: 480, //   8.0 - 12.0
  more: 720, //      12.0 - 15.0
  orbit: 900, //     15.0 - 20.0
  dashboard: 1200, //20.0 - 25.0
  tagline: 1500, //  25.0 - 28.0
  logo: 1680, //     28.0 - 33.0
  end: 1980,
} as const;

export const dur = {
  hook: T.oneTap - T.hook,
  oneTap: T.press - T.oneTap,
  press: T.verdict - T.press,
  verdict: T.more - T.verdict,
  more: T.orbit - T.more,
  orbit: T.dashboard - T.orbit,
  dashboard: T.tagline - T.dashboard,
  tagline: T.logo - T.tagline,
  logo: T.end - T.logo,
} as const;

// Reusable soft radial cream→blush background used across scenes.
// Centred a little high so the hero sits in a pool of light in a tall frame.
export const BG_RADIAL = `radial-gradient(circle at 50% 38%, ${COLORS.white} 0%, ${COLORS.cream} 42%, ${COLORS.creamDeep} 100%)`;
