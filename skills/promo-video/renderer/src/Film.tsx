import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { Finish } from "./components/Atmosphere";
import { FontLoader } from "./components/FontLoader";
import { SCENES } from "./scenes";
import { StyleProvider } from "./style";
import { TransitionFrame } from "./transitions";
import type { RenderConfig } from "./types";

// The film is data: render-config.json (compiled from timeline.json) decides every scene,
// duration, transition and event time. This component only lays the scenes on the clock.
// The same film renders at 16:9, 9:16 and 1:1; scenes adapt through useLayout().
export const Film: React.FC<RenderConfig> = (rc) => {
  const scenes = rc.scenes;
  return (
    <StyleProvider style={rc.style}>
      <AbsoluteFill style={{ backgroundColor: rc.style.ground }}>
        <FontLoader />
        {scenes.map((scene, i) => {
          const next = scenes[i + 1];
          const exit = next
            ? next.transition
            : { type: "none" as const, frames: 0 };
          const Component = SCENES[scene.kind];
          return (
            <Sequence
              key={scene.id}
              from={scene.from}
              durationInFrames={scene.durationInFrames + exit.frames}
              name={`${i + 1} ${scene.id}`}
            >
              <TransitionFrame
                enter={scene.transition}
                exit={exit}
                duration={scene.durationInFrames}
              >
                <Component scene={scene} seedBase={rc.seed * 1000 + i} />
              </TransitionFrame>
            </Sequence>
          );
        })}
        <Finish />
        {rc.audio?.src ? <Audio src={staticFile(rc.audio.src)} /> : null}
      </AbsoluteFill>
    </StyleProvider>
  );
};
