"""SCREENSHOT_MANIFEST.json: every candidate screen, where it came from, and whether it goes in.

Sources are kept apart and never relabelled:
  captured      taken from the product running here (browser or simulator)
  supplied      a screenshot already in the repository, or one the user gave us
  illustration  made for the film; never presented as a real screen

Selection scores each candidate for relevance (what the screen is), clarity (does it show
anything), readability (resolution for the film), uniqueness (not a near-duplicate of a
better one) and safety (account / billing / settings screens and screens with a runtime
error or an auth wall are held back). Every candidate keeps a one-line reason. A person
(or the agent) can override with `promo select --approve/--reject`.
"""
from __future__ import annotations

import re
import time
from pathlib import Path

from .util import PromoError, ffprobe_json, read_json, write_json

SOURCES = {"captured", "supplied", "illustration"}
HIGH = re.compile(r"(^|[/_-])(home|index|dashboard|overview|report|result|results|analytics|editor|workspace|"
                  r"scan|feed|main|app|studio|board|insights|summary)($|[/_.-])", re.I)
MEDIUM = re.compile(r"(^|[/_-])(feature|features|history|detail|upload|create|new|compare|library|search|"
                    r"projects?|items?|onboarding|welcome|success|done|share|export)($|[/_.-])", re.I)
LOW = re.compile(r"(^|[/_-])(settings|account|profile|billing|payment|login|signin|signup|register|auth|"
                 r"password|terms|privacy|legal|404|error|admin)($|[/_.-])", re.I)
SENSITIVE = re.compile(r"(^|[/_-])(settings|account|profile|billing|payment|admin|users?|team|invoices?)($|[/_.-])", re.I)
MIN_W = {"web": 1280, "mobile": 600}
MAX_SELECTED = 6


def image_facts(path: Path) -> dict:
    """Width, height and codec of a real image; raises on anything that is not one."""
    if not path.is_file() or path.stat().st_size == 0:
        raise PromoError(f"screenshot {path.name} is missing or empty")
    try:
        info = ffprobe_json(path)
    except PromoError as exc:
        raise PromoError(f"{path.name} is not a readable image") from exc
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v or not v.get("width") or v.get("codec_name") not in ("png", "mjpeg", "webp", "gif", "bmp", "tiff"):
        raise PromoError(f"{path.name} is not a still image")
    return {"width": int(v["width"]), "height": int(v["height"]), "format": v["codec_name"], "bytes": path.stat().st_size}


def entry(ws_root: Path, path: Path, *, sid: str, product: str, platform: str, screen: str, source: str,
          route: str | None = None, feature: str | None = None, state: str | None = None,
          limitations: list[str] | None = None, captured_at: float | None = None) -> dict:
    if source not in SOURCES:
        raise PromoError(f"unknown screenshot source '{source}'")
    facts = image_facts(path)
    return {"id": sid, "path": path.resolve().relative_to(ws_root.resolve()).as_posix(), "product": product,
            "platform": platform, "screen": screen, "route": route,
            "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(captured_at or path.stat().st_mtime)),
            "width": facts["width"], "height": facts["height"], "bytes": facts["bytes"],
            "source": source, "genuine": source in ("captured", "supplied"),
            "feature": feature, "state": state, "limitations": list(limitations or []),
            "approved": False, "selected": False, "reason": None, "score": None}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "home"


def _luma(path: Path):
    from .reference import SIG_H, SIG_W, _frame_at, _luma as luma
    raw = _frame_at(path, 0, SIG_W, SIG_H)
    return luma(raw) if raw else None


def select(manifest: dict, ws_root: Path, *, max_selected: int = MAX_SELECTED) -> dict:
    """Score every candidate and mark the strongest genuine screens selected and approved."""
    from .reference import _mad, _z, detail
    shots = manifest["screenshots"]
    lumas = {}
    for s in shots:
        name = f"{s.get('route') or ''} {s['screen']} {s['id']}"
        score, why = 0.0, []
        if HIGH.search(name):
            score += 3
            why.append("a primary screen")
        elif MEDIUM.search(name):
            score += 2
            why.append("a feature screen")
        elif LOW.search(name):
            score -= 2
            why.append("an account / auth / legal screen")
        else:
            score += 1
        if s.get("route") in ("/", "") or s["screen"] in ("home", "launch"):
            score += 1
        y = _luma(ws_root / s["path"])
        lumas[s["id"]] = y
        d = detail(y) if y else 0.0
        s["detail"] = round(d, 5)
        if d < 0.0015:
            score -= 4
            why.append("almost empty")
        kind = "mobile" if s["platform"] in ("ios", "android", "flutter", "mobile") else "web"
        if s["width"] < MIN_W[kind] / 2:
            score -= 4
            why.append(f"too small to read in the film ({s['width']} px wide)")
        elif s["width"] < MIN_W[kind]:
            score -= 1
            why.append(f"low resolution ({s['width']} px wide)")
        blockers = [x for x in s["limitations"] if re.search(r"error|auth|login|blank|404|500|unavailable", x, re.I)]
        if blockers:
            score -= 10
            why.append(blockers[0])
        if SENSITIVE.search(name):
            s["sensitive"] = "review: may show personal or account data"
            score -= 3
            why.append("may show account data")
        s["score"] = round(score, 2)
        s["_why"] = why
    chosen: list[dict] = []
    for s in sorted(shots, key=lambda x: (-x["genuine"], -x["score"], x["id"])):
        if s.get("override") in ("approved", "rejected"):
            continue
        # Structure, not mean brightness: light UIs share most of their pixels (the background).
        dup = next((c for c in chosen if lumas.get(c["id"]) and lumas.get(s["id"]) and
                    _mad(_z(lumas[c["id"]]), _z(lumas[s["id"]])) < 0.10), None)
        if dup:
            s.update(selected=False, approved=False, reason=f"near-duplicate of {dup['id']}")
        elif not s["genuine"]:
            s.update(selected=False, approved=False,
                     reason="illustration: usable only in a scene marked illustrative, never as a real screen")
        elif s["score"] <= 0 or len(chosen) >= max_selected:
            s.update(selected=False, approved=False,
                     reason="; ".join(s["_why"]) or ("lower priority than the selected screens" if s["score"] > 0 else "not useful"))
        else:
            s.update(selected=True, approved=True, reason="selected: " + ("; ".join(s["_why"]) or "useful screen"))
            chosen.append(s)
    for s in shots:
        if s.get("override") == "approved":
            s.update(selected=True, approved=True, reason=f"approved by hand: {s.get('overrideReason') or 'no reason given'}")
        elif s.get("override") == "rejected":
            s.update(selected=False, approved=False, reason=f"rejected by hand: {s.get('overrideReason') or 'no reason given'}")
        s.pop("_why", None)
    return manifest


def load(path: Path) -> dict:
    return read_json(path) if path.exists() else {"version": 1, "stage": None, "screenshots": [], "rejected": []}


def by_id(manifest: dict) -> dict[str, dict]:
    return {s["id"]: s for s in manifest.get("screenshots", [])}


def save(path: Path, manifest: dict) -> None:
    write_json(path, manifest)
