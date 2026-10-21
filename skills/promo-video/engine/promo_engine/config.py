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
    # Mode is derived from this, never chosen: kind "none" → autonomous, anything else → reference.
    "reference": {"kind": None, "source": None},
    "inspiration": {"url": None},  # v4 name for a YouTube reference; read for compatibility
    # The one audio policy every step obeys. `music` exists only to be false.
    "audio": {"voiceover": None, "soundEffects": None, "music": False},
    # Decisions the user made (or supplied up front); `promo questions` never asks these again.
    "decided": [],
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
    # App Store app previews: exact device sizes, never a letterboxed 1080-wide file.
    "store-portrait": {"id": "PromoStorePortrait", "width": 886, "height": 1920},
    "store-landscape": {"id": "PromoStoreLandscape", "width": 1920, "height": 886},
}

QUALITY = {
    "draft": {"crf": 28, "scale": 0.5},
    "final": {"crf": 18, "scale": 1.0},
}

def render_scale(aspect: str, quality: str) -> float:
    """The quality's scale, unless it would give an odd side (H.264 4:2:0 needs even sizes):
    886 × 0.5 = 443, so App Store drafts render at full size."""
    s = QUALITY[quality]["scale"]
    a = ASPECTS[aspect]
    w, h = a["width"] * s, a["height"] * s
    return s if w == int(w) and h == int(h) and int(w) % 2 == 0 and int(h) % 2 == 0 else 1.0


VOICE_PROVIDERS = {"auto", "openrouter", "openai", "say", "files", "none"}
# Which environment variable unlocks each API provider. Values are never read into config.
PROVIDER_KEYS = {"openrouter": "OPENROUTER_API_KEY", "openai": "OPENAI_API_KEY"}

# The three audio choices offered to the user, and nothing else. Music is never a choice.
AUDIO_MODES = {
    "voiceover": {"voiceover": True, "soundEffects": True},
    "effects": {"voiceover": False, "soundEffects": True},
    "silent": {"voiceover": False, "soundEffects": False},
}
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
    def qa_report(self) -> Path: return self.root / "TEST_REPORT.md"

    def config(self) -> dict:
        user = read_json(self.config_path) if self.config_path.exists() else {}
        cfg = _merge(DEFAULTS, user)
        validate_config(cfg)
        return normalise(cfg)

    @property
    def product_root(self) -> Path:
        return (self.root / (self.config()["product"].get("root") or "..")).resolve()

    @property
    def out_dir(self) -> Path:
        return (self.root / self.config()["render"]["outputDir"]).resolve()


def normalise(cfg: dict) -> dict:
    """Fill derived fields so every step reads one shape (v4 workspaces included)."""
    ref = cfg["reference"]
    if ref.get("kind") is None and cfg["inspiration"].get("url"):
        cfg["reference"] = {"kind": "youtube", "source": cfg["inspiration"]["url"]}
    if cfg["audio"].get("voiceover") is None:
        # v4 had no audio choice: narration unless the provider was 'none', effects always.
        cfg["audio"] = {"voiceover": cfg["voice"]["provider"] != "none", "soundEffects": True, "music": False}
    return cfg


def mode(cfg: dict) -> str:
    """'reference' when a reference video was supplied, else 'autonomous'."""
    return "reference" if cfg["reference"].get("kind") not in (None, "none") else "autonomous"


def reference_source(cfg: dict) -> str | None:
    return cfg["reference"].get("source") if mode(cfg) == "reference" else None


def audio_mode(cfg: dict) -> str:
    a = cfg["audio"]
    for name, flags in AUDIO_MODES.items():
        if (a["voiceover"], a["soundEffects"]) == (flags["voiceover"], flags["soundEffects"]):
            return name
    raise PromoError("invalid audio configuration")  # unreachable after validate_config


def validate_audio(audio: dict) -> None:
    """Music can never be enabled; only the three offered combinations are valid."""
    if audio.get("music") is not False:
        raise PromoError("audio.music must be false: background music is never used, in any mode",
                         hint="remove the music setting from promo.config.json")
    extra = set(audio) - {"voiceover", "soundEffects", "music"}
    if extra:
        raise PromoError(f"unknown audio setting(s): {', '.join(sorted(extra))}",
                         hint="audio holds only voiceover, soundEffects and music:false")
    vo, fx = audio.get("voiceover"), audio.get("soundEffects")
    if vo is None and fx is None:
        return  # undecided: filled by normalise() for v4 workspaces, or asked by `promo questions`
    if not isinstance(vo, bool) or not isinstance(fx, bool):
        raise PromoError("audio.voiceover and audio.soundEffects must be true or false")
    if vo and not fx:
        raise PromoError("voice-over without sound effects is not one of the offered audio modes",
                         hint="use `--audio voiceover` (voice + effects), `effects`, or `silent`")


def validate_config(cfg: dict) -> None:
    validate_audio(cfg["audio"])
    kind = cfg["reference"].get("kind")
    if kind not in (None, "none", "youtube", "url", "file"):
        raise PromoError(f"unknown reference kind '{kind}'")
    if kind in ("youtube", "url", "file") and not cfg["reference"].get("source"):
        raise PromoError("reference has a kind but no source")
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


def _decide(cfg: dict, key: str) -> None:
    if key not in cfg.setdefault("decided", []):
        cfg["decided"].append(key)


def init_workspace(ws: Workspace, *, product_root: Path, name: str | None = None,
                   inspiration_url: str | None = None, reference: dict | None = None,
                   audio: str | None = None, provider: str | None = None,
                   aspects: list[str] | None = None, runtime: tuple[int, int] | None = None) -> Path:
    """Create the workspace and a config seeded with what we already know.

    Every argument given is recorded as decided, so it is never asked again. Values are
    validated before anything is written.
    """
    ws.root.mkdir(parents=True, exist_ok=True)
    (ws.assets).mkdir(exist_ok=True)
    root_value = os.path.relpath(Path(product_root).resolve(), ws.root)
    existing = read_json(ws.config_path) if ws.config_path.exists() else {}
    cfg = _merge(existing, {"product": {"root": root_value}})
    if name:
        cfg = _merge(cfg, {"product": {"name": name}})
        _decide(cfg, "product")
    if inspiration_url is not None and reference is None:
        reference = {"kind": "youtube" if inspiration_url else "none", "source": inspiration_url or None}
    if reference is not None:
        cfg["reference"] = reference
        cfg = _merge(cfg, {"inspiration": {"url": reference["source"] if reference["kind"] == "youtube" else None}})
        _decide(cfg, "reference")
    if audio is not None:
        if audio not in AUDIO_MODES:
            raise PromoError(f"unknown audio mode '{audio}'", hint=f"use one of {', '.join(AUDIO_MODES)}")
        cfg["audio"] = {**AUDIO_MODES[audio], "music": False}
        _decide(cfg, "audio")
        if audio != "voiceover":
            cfg = _merge(cfg, {"voice": {"provider": "none"}})
            _decide(cfg, "provider")
    if provider is not None:
        if provider not in VOICE_PROVIDERS - {"auto", "none"}:
            raise PromoError(f"unknown voice provider '{provider}'")
        cfg = _merge(cfg, {"voice": {"provider": provider}})
        _decide(cfg, "provider")
    if aspects:
        cfg = _merge(cfg, {"format": {"aspects": list(dict.fromkeys(aspects))}})
        _decide(cfg, "formats")
    if runtime:
        cfg = _merge(cfg, {"duration": {"min": runtime[0], "max": runtime[1]}})
        _decide(cfg, "runtime")
    validate_config(_merge(DEFAULTS, cfg))
    write_json(ws.config_path, cfg)
    gi = ws.root / ".gitignore"
    if not gi.exists():
        gi.write_text("# regenerable pipeline output\nbuild/\nout/\nqa/frames/\nqa/stills/\ninspiration/watch/\n"
                     "# third-party transcript and local paths: regenerate with `promo watch`\n"
                     "inspiration/evidence.json\ninspiration/watch-report.md\n")
    return ws.config_path
