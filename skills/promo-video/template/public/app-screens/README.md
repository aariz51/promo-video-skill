# app-screens

Drop your app's screenshots here as PNGs (clean, real screens — the dashboard/home, the
core "money-shot" result screen, and the key feature screens).

Then map them in `src/theme.ts` → `screens`, e.g.:

```ts
export const screens = {
  dashboard: "app-screens/01-home.png",
  result:    "app-screens/02-result.png",
  // …
} as const;
```

Screens are portrait phone captures (`SCREEN_RATIO` ≈ 0.4615 in theme.ts). The scenes
`objectFit: cover` from the top, so full-height captures look best.
