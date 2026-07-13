import React from "react";

// Cartoon hand-cursor that travels and presses real UI — the reference's key
// "product demo" device. `pressed` 0→1 scales it down like a click.
export const Cursor: React.FC<{
  x: number;
  y: number;
  scale?: number;
  pressed?: number; // 0..1
  rotation?: number;
}> = ({ x, y, scale = 1, pressed = 0, rotation = -8 }) => {
  const press = 1 - pressed * 0.16;
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-18%, -8%) rotate(${rotation}deg) scale(${scale * press})`,
        transformOrigin: "20% 20%",
        filter: "drop-shadow(0 8px 14px rgba(43,45,66,0.28))",
        pointerEvents: "none",
      }}
    >
      <svg width="60" height="76" viewBox="0 0 60 76" fill="none">
        {/* pointing-hand cursor */}
        <path
          d="M20 6c0-3 5-3 5 0v22l4-9c1-3 6-1 5 2l-2 8h4c3 0 5 1 7 3l6 7c2 3 2 7 1 11l-3 12c-1 4-5 7-9 7H26c-4 0-7-2-9-5L6 50c-2-3-1-6 2-7 2-1 4 0 6 2l6 6V6z"
          fill="#FFFFFF"
          stroke="#2B2D42"
          strokeWidth="3"
          strokeLinejoin="round"
        />
      </svg>
      {/* tap ripple on press */}
      {pressed > 0.02 ? (
        <div
          style={{
            position: "absolute",
            left: 6,
            top: 8,
            width: 40 * scale,
            height: 40 * scale,
            marginLeft: -20 * scale,
            marginTop: -20 * scale,
            borderRadius: "50%",
            border: `3px solid rgba(122,31,162,${0.6 * (1 - pressed)})`,
            transform: `scale(${0.4 + pressed * 1.6})`,
          }}
        />
      ) : null}
    </div>
  );
};
