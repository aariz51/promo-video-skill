import React from "react";
import type { Scene, SceneKind } from "../types";
import { Compare } from "./Compare";
import { DocumentScene } from "./DocumentScene";
import { Flow } from "./Flow";
import { Hook } from "./Hook";
import { Lockup } from "./Lockup";
import { Metric } from "./Metric";
import { Montage } from "./Montage";
import { Pillars } from "./Pillars";
import { Screen } from "./Screen";
import { Statement } from "./Statement";
import { Terminal } from "./Terminal";
import { Title } from "./Title";
import { WordZoom } from "./WordZoom";

// Every kind the engine accepts (engine/promo_engine/timeline.py KINDS) must be here;
// tests/test_renderer_contract.py enforces it.
export const SCENES: Record<
  SceneKind,
  React.FC<{ scene: Scene; seedBase: number }>
> = {
  hook: Hook,
  wordzoom: WordZoom,
  title: Title,
  statement: Statement,
  pillars: Pillars,
  screen: Screen,
  flow: Flow,
  terminal: Terminal,
  document: DocumentScene,
  montage: Montage,
  compare: Compare,
  metric: Metric,
  lockup: Lockup,
};
