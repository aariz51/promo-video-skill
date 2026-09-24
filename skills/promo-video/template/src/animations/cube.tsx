import React, { useLayoutEffect, useRef } from "react";
import { getInputProps, useCurrentFrame, useVideoConfig } from "remotion";
import { leave, morph, rise } from "cube-motion";

// ════════════════════════════════════════════════════════════════════════════
//  Cube Motion, driven by the Remotion clock.
//
//  cube-motion (https://www.cube-motion.dev) ships four opinionated UI motions:
//  rise (enter), leave (exit), morph (state change) and reveal (rise on scroll).
//  Duration, curve and distance are fixed by the library — only stagger and delay
//  are configurable — which is why it is useful here: every UI element in the film
//  enters, exits and changes state with one consistent, well-judged feel.
//
//  The catch: cube-motion is TIME-based (Web Animations API). Remotion renders each
//  frame independently, often out of order and across several browser tabs, so a
//  wall-clock animation would be captured at an arbitrary moment.
//
//  The bridge: every cube-motion function RETURNS its WAAPI `Animation` objects. We
//  create them once on mount, pause them, and on every frame set
//  `currentTime = (frame - at) / fps`. The library still owns the keyframes, the
//  curve, the stagger and the fill modes; Remotion owns the clock. Deterministic and
//  frame-accurate.
//
//  Division of labour inside `animations/`:
//    springs.ts / easings.ts / motion.ts → cinematic motion: devices, cameras, hero
//                                          objects — anything whose travel scales
//                                          with the frame.
//    cube.tsx                            → the UI layer: labels, chips, list rows,
//                                          captions, badges, and text that changes.
//
//  `reveal` is not wrapped: it waits for an IntersectionObserver (scroll), and a video
//  has no scroll. <CubeRise at={…}> is its video equivalent.
//
//  Render with `--props='{"cube":false}'` to switch every cube motion off (elements
//  render in their resting state). That switch exists to show, frame by frame, what
//  the library contributes.
// ════════════════════════════════════════════════════════════════════════════

export const cubeEnabled = (): boolean => (getInputProps() as { cube?: boolean }).cube !== false;

/**
 * Let cube-motion build its animations once, then scrub them with the Remotion frame.
 * Several clocks may share one element as long as they animate different nodes.
 */
function useCubeClock<T extends Element>(
  ref: React.RefObject<T | null>,
  create: ((el: T) => Animation[]) | null,
  at: number,
): void {
  const anims = useRef<Animation[]>([]);
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !create || !cubeEnabled()) return;
    const created = create(el);
    created.forEach((a) => {
      a.pause();
      a.finished.catch(() => {}); // cancelled on unmount; not an error
    });
    anims.current = created;
    return () => {
      created.forEach((a) => a.cancel());
      anims.current = [];
    };
    // One set of animations per mount, by design: `at` and options are fixed per instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Declared after the mount effect, so on mount it runs second and seeks the new set.
  useLayoutEffect(() => {
    const t = Math.max(0, ((frame - at) / fps) * 1000);
    for (const a of anims.current) a.currentTime = t;
  });
}

type Common = { style?: React.CSSProperties; className?: string; children?: React.ReactNode };

/** Fade and lift in — cube-motion `rise`. `at` is a frame inside the enclosing <Sequence>. */
export const CubeRise: React.FC<Common & { at: number }> = ({ at, style, className, children }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  useCubeClock(ref, (el) => rise(el), at);
  return <div ref={ref} style={style} className={className}>{children}</div>;
};

/** Fade and drop out — cube-motion `leave`. Holds hidden once finished. */
export const CubeLeave: React.FC<Common & { at: number }> = ({ at, style, className, children }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  useCubeClock(ref, (el) => leave(el), at);
  return <div ref={ref} style={style} className={className}>{children}</div>;
};

/**
 * Rise in at `at`, leave at `outAt`. rise and leave each clear their own element's
 * animations, so they sit on two nested nodes: leave outside, rise inside.
 */
export const CubeInOut: React.FC<Common & { at: number; outAt: number }> = ({ at, outAt, style, className, children }) => (
  <CubeLeave at={outAt} style={style} className={className}>
    <CubeRise at={at}>{children}</CubeRise>
  </CubeLeave>
);

/**
 * A list whose items rise in sequence and (optionally) leave in sequence, using the
 * library's own stagger (rise 70ms, leave 40ms unless overridden). Each item gets two
 * nodes — an outer one `leave` targets and an inner one `rise` targets — so the two
 * motions never cancel each other.
 */
export const CubeList: React.FC<Common & {
  at: number;
  outAt?: number;
  /** ms between items entering (library default 70). */
  stagger?: number;
  itemStyle?: React.CSSProperties;
}> = ({ at, outAt, stagger, style, className, itemStyle, children }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  useCubeClock(
    ref,
    (el) => rise(el.querySelectorAll(":scope > [data-cube-item] > [data-cube-inner]"),
      stagger !== undefined ? { stagger } : {}),
    at,
  );
  useCubeClock(
    ref,
    outAt === undefined ? null : (el) => leave(el.querySelectorAll(":scope > [data-cube-item]")),
    outAt ?? 0,
  );
  return (
    <div ref={ref} style={style} className={className}>
      {React.Children.toArray(children).map((child, i) => (
        <div key={i} data-cube-item="" style={itemStyle}>
          <div data-cube-inner="">{child}</div>
        </div>
      ))}
    </div>
  );
};

/**
 * Text that changes state — cube-motion `morph`. Shows `from` until `at`; then the
 * letters that differ blur out and the new ones blur in, per grapheme, while the
 * wrapper's width follows the new text. Shared leading letters stay put.
 */
export const CubeMorphText: React.FC<{ at: number; from: string; to: string; style?: React.CSSProperties }> = ({
  at,
  from,
  to,
  style,
}) => {
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  const outRef = useRef<HTMLSpanElement | null>(null);
  const inRef = useRef<HTMLSpanElement | null>(null);
  useCubeClock(
    wrapRef,
    () => (outRef.current && inRef.current ? morph(outRef.current, inRef.current) : []),
    at,
  );
  const on = cubeEnabled();
  return (
    <span ref={wrapRef} style={{ display: "inline-block", position: "relative", whiteSpace: "pre", ...style }}>
      {on ? <span ref={outRef}>{from}</span> : null}
      <span ref={inRef} style={on ? { position: "absolute", left: 0, top: 0, opacity: 0 } : undefined}>{to}</span>
    </span>
  );
};

/**
 * A label that cycles through several states — e.g. a feature pill reading
 * "Kick counter" → "Due date" → "Hospital bag". `at[i]` is the frame at which
 * `labels[i + 1]` morphs in. One morph pair is mounted at a time.
 */
export const CubeMorphSequence: React.FC<{ labels: string[]; at: number[]; style?: React.CSSProperties }> = ({
  labels,
  at,
  style,
}) => {
  const frame = useCurrentFrame();
  let step = 0;
  for (let i = 0; i < at.length; i++) if (frame >= at[i] - 1) step = i;
  return (
    <CubeMorphText
      key={step}
      at={at[step]}
      from={labels[step]}
      to={labels[Math.min(step + 1, labels.length - 1)]}
      style={style}
    />
  );
};
