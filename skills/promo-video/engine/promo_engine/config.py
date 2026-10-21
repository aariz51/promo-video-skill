"""Workspace layout and configuration.

Everything the pipeline produces lives in one workspace folder inside the product repo
(`<product>/promo/` by default), so every intermediate artifact can be inspected.
Configuration is `promo/promo.config.json`; secrets only ever come from the environment.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .util import PromoError, read_json, write_json

DEFAULTS: dict[str, Any] = {
    "product": {"name": None, "description": None, "root": ".."},
    "inspiration": {"url": None},
    "duration": {"min": 60, "max": 100},
    "format": {"aspects": ["16:9"], "fps": 30},
    "style": {"preset": "graphite", "accent": None},
    "voice": {
        "provider": "auto",  # auto | openrouter | say | files | none
        "voice": None,
        "direction": "Calm, confident, precise. A premium product film, never salesy.",
    },
    "sound": {"ambience": False},
    "render": {"quality": "final", "outputDir": "out"},
    "seed": 1,
}

ASPECTS = {
    "16:9": {"id": "Promo16x9", "width": 1920, "height": 1080},
    "9:16": {"id": "Promo9x16", "width": 1080, "height": 1920},
    "1:1": {"id": "Promo1x1", "width": 1080, "height": 1080},
}

QUALITY = {
    "draft": {"crf": 28, "scale": 0.5},
    "final": {"crf": 18, "scale": 1.0},
}

VOICE_PROVIDERS = {"auto", "openrouter", "say", "files", "none"}
STYLE_PRESETS = {"graphite", "paper", "midnight"}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Workspace:
    """The promo workspace: one folder of artifacts per product."""

    root: Path

    @classmethod
    def at(cls, path: str | Path) -> "Workspace":
        return cls(Path(path).expanduser().resolve())

    # Artifacts, in pipeline order.
    @property
    def config_path(self) -> Path: return self.root / "promo.config.json"
    @property
    def scan(self) -> Path: return self.root / "product-scan.json"
    @property
    def brief(self) -> Path: return self.root / "product-brief.md"
    @property
    def inspiration_dir(self) -> Path: return self.root / "inspiration"
    @property
    def evidence(self) -> Path: return self.inspiration_dir / "evidence.json"
    @property
    def inspiration(self) -> Path: return self.root / "inspiration-analysis.md"
    @property
    def creative(self) -> Path: return self.root / "creative-prompt.md"
    @property
    def timeline(self) -> Path: return self.root / "timeline.json"
    @property
    def storyboard(self) -> Path: return self.root / "storyboard.md"
    @property
    def narration(self) -> Path: return self.root / "narration.txt"
    @property
    def render_config(self) -> Path: return self.root / "render-config.json"
    @property
    def assets(self) -> Path: return self.root / "assets"
    @property
    def stage(self) -> Path: return self.root / "build" / "public"
    @property
    def vo_dir(self) -> Path: return self.stage / "audio" / "vo"
    @property
    def master_audio(self) -> Path: return self.stage / "audio" / "master.wav"
    @property
    def qa_dir(self) -> Path: return self.root / "qa"
    @property
    def qa_report(self) -> Path: return self.root / "qa-report.md"

    def config(self) -> dict:
        user = read_json(self.config_path) if self.config_path.exists() else {}
        cfg = _merge(DEFAULTS, user)
        validate_config(cfg)
        return cfg

    @property
    def product_root(self) -> Path:
        return (self.root / (self.config()["product"].get("root") or "..")).resolve()

    @property
    def out_dir(self) -> Path:
        return (self.root / self.config()["render"]["outputDir"]).resolve()


def validate_config(cfg: dict) -> None:
    for a in cfg["format"]["aspects"]:
        if a not in ASPECTS:
            raise PromoError(f"unsupported aspect '{a}'", hint=f"use one of {', '.join(ASPECTS)}")
    if cfg["render"]["quality"] not in QUALITY:
        raise PromoError(f"unknown render quality '{cfg['render']['quality']}'", hint="use draft or final")
    if cfg["voice"]["provider"] not in VOICE_PROVIDERS:
        raise PromoError(f"unknown voice provider '{cfg['voice']['provider']}'",
                         hint=f"use one of {', '.join(sorted(VOICE_PROVIDERS))}")
    if cfg["style"]["preset"] not in STYLE_PRESETS:
        raise PromoError(f"unknown style preset '{cfg['style']['preset']}'",
                         hint=f"use one of {', '.join(sorted(STYLE_PRESETS))}")
    d = cfg["duration"]
    if not (10 <= d["min"] <= d["max"] <= 300):
        raise PromoError("duration must satisfy 10 <= min <= max <= 300 seconds")
    if int(cfg["format"]["fps"]) not in (24, 25, 30, 60):
        raise PromoError("fps must be 24, 25, 30 or 60")


def init_workspace(ws: Workspace, *, product_root: Path, name: str | None = None,
                   inspiration_url: str | None = None) -> Path:
    """Create the workspace and a config seeded with what we already know."""
    ws.root.mkdir(parents=True, exist_ok=True)
    (ws.assets).mkdir(exist_ok=True)
    root_value = os.path.relpath(Path(product_root).resolve(), ws.root)
    existing = read_json(ws.config_path) if ws.config_path.exists() else {}
    cfg = _merge(existing, {"product": {"root": root_value}})
    if name:
        cfg = _merge(cfg, {"product": {"name": name}})
    if inspiration_url is not None:
        cfg = _merge(cfg, {"inspiration": {"url": inspiration_url}})
    write_json(ws.config_path, cfg)
    gi = ws.root / ".gitignore"
    if not gi.exists():
        gi.write_text("# regenerable pipeline output\nbuild/\nout/\nqa/frames/\nqa/stills/\ninspiration/watch/\n"
                     "# third-party transcript and local paths: regenerate with `promo watch`\n"
                     "inspiration/evidence.json\ninspiration/watch-report.md\n")
    return ws.config_path
