// ════════════════════════════════════════════════════════════════════════════
//  BRAND SYSTEM + FILM TIMING — the single source of truth for the whole film.
//  ► To retarget this template to a new app, this is the FIRST file to edit:
//    swap COLORS for the app's palette, point `screens`/`LOGO` at its assets,
//    and (optionally) pick fonts in ./fonts.ts. Keep `T`/`dur` unchanged so the
//    prebuilt audio stays in sync — or change them and rebuild audio to match.
//  The shipped values are a deliberately neutral placeholder identity, so the
//  template renders on a fresh clone with no assets of your own.
// ════════════════════════════════════════════════════════════════════════════
import { FONT_HEAD, FONT_BODY } from "./fonts";

export { FONT_HEAD, FONT_BODY };

export const COLORS = {
  // Base (background system) — near-white with a cool tint.
  cream: "#F7F8FC",
  creamDeep: "#EEF0F8",
  blush: "#E3E6F5",
  // Brand primary / secondary / accent — replace with the app's sampled palette.
  purple: "#4F46E5",
  purpleSoft: "#7A75EE",
  purpleDeep: "#3730A3",
  pink: "#DB2777",
  pinkSoft: "#F472B6",
  gold: "#F59E0B",
  goldSoft: "#FCD34D",
  // Result semantics (good / warn / bad) — recolour for your domain.
  safe: "#10B981",
  safeSoft: "#6EE7B7",
  caution: "#F97316",
  avoid: "#EF4444",
  // Ink
  ink: "#1E2230",
  inkSoft: "#7A8296",
  white: "#FFFFFF",
} as const;

// Canvas — 9:16 vertical (App Store preview / Reels / TikTok / Shorts / Stories).
export const FPS = 60;
export const WIDTH = 1080;
export const HEIGHT = 1920;
export const DURATION = 1980; // 33s — keep in sync with DUR in scripts/build_audio.py

// Native app-screen dimensions (portrait phone)
export const SCREEN_W = 1080;
export const SCREEN_H = 2340;
export const SCREEN_RATIO = SCREEN_W / SCREEN_H; // ~0.4615

// The seven screens the shipped scenes use: one hero (`dashboard`, the money
// shot in S7) and six that ride the orbit ring in S6. Drop your PNGs into
// public/app-screens/ and repoint these — the keys are what the scenes import,
// so keep the key names and change only the file paths.
// The shipped files are generated stand-ins (scripts/make_placeholders.py).
export const screens = {
  dashboard: "app-screens/01-home.png",
  detail: "app-screens/02-detail.png",
  search: "app-screens/03-search.png",
  library: "app-screens/04-library.png",
  profile: "app-screens/05-profile.png",
  settings: "app-screens/06-settings.png",
  result: "app-screens/07-result.png",
} as const;

export const LOGO = "logo/app-logo.png";

// The pre-mixed audio master (VO + SFX + pad), built by scripts/build_audio.py.
// Ships as null so a fresh clone renders silently instead of failing on a file
// that does not exist yet. Set this to "audio/master.wav" AFTER you have run
// `npm run audio`.
export const AUDIO_SRC: string | null = null;

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

// Reusable soft radial background used across scenes.
// Centred a little high so the hero sits in a pool of light in a tall frame.
export const BG_RADIAL = `radial-gradient(circle at 50% 38%, ${COLORS.white} 0%, ${COLORS.cream} 42%, ${COLORS.creamDeep} 100%)`;
