"""Layer 6: STORYBOARD / TIMELINE ENGINE.

`timeline.json` is the film, authored by the agent from the PRODUCT-SPECIFIC PROMO PROMPT:
an ordered list of scenes, each a primitive (`kind`) with props, a duration, a transition,
optional narration and the claim ids that back what it shows.

`compile_timeline()` validates it and produces everything downstream consumes:

- `render-config.json`: frames, compositions, resolved style, scene props plus the exact
  time of every in-scene event (`props._t`), sound cues and narration cues.
- `storyboard.md` and `narration.txt`: human-readable views of the same data.

The renderer never invents its own timings; it reads `_t`. The mixer reads the same
cues. Picture and sound therefore share one clock, in every aspect ratio.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import sound
from .analyzer import image_size
from .artifacts import parse_claims
from .config import ASPECTS, QUALITY, Workspace
from .util import PromoError, Report, ffprobe_json, fmt_time, read_json, write_json

MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", ".mov", ".webm", ".m4v"}
TRANSITIONS = {"none", "cut", "fade", "light", "push", "wipe", "zoom"}
DEVICES = {"browser", "phone", "desktop", "none"}
CAMERAS = {"push", "pan", "hold", "pull", "rise"}
SPEECH_WPS = 2.7  # a calm, cinematic read

# kind → (required props, text limits {prop: max chars}, list limits {prop: (min, max)})
KINDS: dict[str, dict] = {
    "hook": {"req": ["line"], "text": {"line": 70, "eyebrow": 40}, "lists": {"fragments": (0, 16)}},
    "wordzoom": {"req": ["line", "word"], "text": {"line": 60, "then": 60, "word": 24, "name": 32}, "lists": {}},
    "title": {"req": ["name"], "text": {"name": 32, "tagline": 70}, "lists": {}},
    "statement": {"req": ["text"], "text": {"text": 90, "eyebrow": 40, "small": 110}, "lists": {}},
    "pillars": {"req": ["items"], "text": {"title": 60}, "lists": {"items": (2, 4)}},
    "screen": {"req": ["media"], "text": {"caption": 80, "title": 60}, "lists": {"callouts": (0, 4)}},
    "flow": {"req": ["steps"], "text": {"title": 60}, "lists": {"steps": (2, 5)}},
    "terminal": {"req": ["lines"], "text": {"title": 40, "caption": 80}, "lists": {"lines": (1, 14)}},
    "document": {"req": ["title", "sections"], "text": {"title": 50, "caption": 80}, "lists": {"sections": (1, 4)}},
    "montage": {"req": ["items"], "text": {"title": 60}, "lists": {"items": (3, 8)}},
    "compare": {"req": ["left", "right"], "text": {"title": 60, "verdict": 70}, "lists": {}},
    "metric": {"req": ["value", "label"], "text": {"label": 60, "small": 110}, "lists": {}},
    "lockup": {"req": ["name"], "text": {"name": 32, "line": 80, "cta": 50, "small": 90}, "lists": {}},
}
_NUM = re.compile(r"\d")


def _texts(obj, path="") -> list[tuple[str, str]]:
    """Every visible string inside props, with its path. Media paths are not visible text."""
    out = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _texts(v, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("media", "logo", "type", "device", "camera", "layout", "icon", "tone") or k.startswith("_"):
                continue
            out += _texts(v, f"{path}.{k}" if path else k)
    return out


def _media_refs(props: dict) -> list[str]:
    refs = []
    for key in ("media", "logo"):
        if isinstance(props.get(key), str):
            refs.append(props[key])
    for coll in ("items", "steps"):
        for it in props.get(coll, []) or []:
            if isinstance(it, dict) and isinstance(it.get("media"), str):
                refs.append(it["media"])
    return refs


def media_aspect(path: Path) -> float:
    """Width / height of an image or video; 16:10 when it cannot be read (e.g. SVG)."""
    if path.suffix.lower() in (".mp4", ".mov", ".webm", ".m4v"):
        try:
            v = next(st for st in ffprobe_json(path)["streams"] if st["codec_type"] == "video")
            return round(v["width"] / v["height"], 5)
        except (PromoError, StopIteration, KeyError, ZeroDivisionError):
            return 1.6
    size = image_size(path)
    return round(size[0] / size[1], 5) if size and size[1] else 1.6


def _schedule(kind: str, p: dict, d: float, where: str, r: Report) -> dict:
    """Seconds (scene-relative) at which each event in the scene happens."""
    if kind == "hook":
        freeze = float(p.get("freezeAt", round(d * 0.55, 2)))
        return {"freeze": freeze, "line": round(freeze + 0.6, 2)}
    if kind == "wordzoom":
        final = p.get("then") or p["line"]
        if p["word"] not in final:
            r.error(where, f"word '{p['word']}' must appear in the {'then' if p.get('then') else 'line'} text")
        type_for = round(min(2.6, max(0.6, len(p["line"]) / 22)), 2)
        t = 0.3 + type_for + 0.5
        out = {"typeFor": type_for}
        if p.get("then"):
            out["then"] = round(t + 0.4, 2)
            t = out["then"] + 0.9
        out.update(cursors=round(0.3 + type_for * 0.6, 2), select=round(t, 2),
                   zoom=[round(t + 0.7, 2), round(t + 2.0, 2)], name=round(t + 2.3, 2))
        if t + 3.2 > d:
            r.error(where, f"wordzoom needs {t + 3.2:.1f}s but the scene is {d:.1f}s")
        return out
    if kind == "title":
        return {"name": 0.5, "tagline": 1.5}
    if kind == "statement":
        return {"text": 0.35, "small": 1.4}
    if kind == "pillars":
        items = [round(0.5 + i * 0.5, 2) for i in range(len(p["items"]))]
        return {"items": items, "focus": round(items[-1] + 0.9, 2)}
    if kind == "screen":
        cs = p.get("callouts", []) or []
        default = [round(1.2 + i * max(0.8, (d - 3.0) / max(1, len(cs))), 2) for i in range(len(cs))]
        out = {"callouts": [float(c.get("at", default[i])) for i, c in enumerate(cs)]}
        if isinstance(p.get("cursor"), dict):
            out["click"] = float(p["cursor"].get("at", d * 0.5))
        return out
    if kind == "flow":
        n = len(p["steps"])
        span = max(1.0, d - 2.2)
        return {"steps": [round(0.5 + i * span / max(1, n - 1), 2) for i in range(n)]}
    if kind == "terminal":
        t, lines = 0.5, []
        for i, ln in enumerate(p["lines"]):
            ln = ln if isinstance(ln, dict) else {"type": "out", "text": str(ln)}
            typ = ln.get("type", "out")
            if typ == "cmd":
                type_for = round(min(2.4, max(0.45, len(ln["text"]) / 28)), 2)
                lines.append({"type": typ, "at": round(t, 2), "typeFor": type_for})
                t += type_for + 0.35
            else:
                lines.append({"type": typ, "at": round(t, 2)})
                t += float(ln.get("hold", 0.28))
        if t > d - 0.6:
            r.error(where, f"terminal content needs {t + 0.6:.1f}s but the scene is {d:.1f}s; lengthen it or cut lines")
        return {"lines": lines}
    if kind == "document":
        n = len(p["sections"])
        return {"sections": [round(0.8 + i * max(0.7, (d - 2.5) / n), 2) for i in range(n)]}
    if kind == "montage":
        return {"items": [round(0.3 + i * 0.14, 2) for i in range(len(p["items"]))]}
    if kind == "compare":
        out = {"left": 0.4, "right": 1.3}
        if p.get("verdict"):
            out["verdict"] = round(max(2.4, d - 2.2), 2)
        return out
    if kind == "metric":
        return {"count": [0.5, 2.1]}
    if kind == "lockup":
        return {"logo": 0.3, "name": 0.8, "line": 1.9, "cta": 3.0}
    return {}


def validate(tl: dict, ws: Workspace, cfg: dict, claims: dict[str, dict]) -> Report:
    r = Report()
    if tl.get("version") != 1:
        r.error("timeline", "version must be 1")
    scenes = tl.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        r.error("timeline", "scenes must be a non-empty list")
        return r
    if tl.get("source") not in ("framework", "inspiration"):
        r.error("timeline", "source must be 'framework' or 'inspiration'")
    style = tl.get("style", {})
    if style.get("preset", cfg["style"]["preset"]) not in ("graphite", "paper", "midnight"):
        r.error("timeline.style", "preset must be graphite, paper or midnight")
    for key in ("accent", "ground", "ink"):
        v = style.get(key)
        if v is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)):
            r.error("timeline.style", f"{key} must be a #rrggbb colour")
    narr = tl.get("narration", {"enabled": True})
    if not narr.get("enabled", True) and not narr.get("reason"):
        r.error("timeline.narration", "narration is disabled without a reason; voiceover is the default")

    ids, total = set(), 0.0
    for i, s in enumerate(scenes):
        where = f"scene[{i}]"
        sid = s.get("id")
        if not sid or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(sid)):
            r.error(where, "id must be a lowercase slug")
        elif sid in ids:
            r.error(where, f"duplicate id '{sid}'")
        ids.add(sid)
        where = f"scene '{sid or i}'"
        kind = s.get("kind")
        if kind not in KINDS:
            r.error(where, f"unknown kind '{kind}' (known: {', '.join(KINDS)})")
            continue
        if not s.get("purpose"):
            r.error(where, "purpose is required (what this scene does for the story)")
        d = s.get("duration")
        if not isinstance(d, (int, float)) or not 1.5 <= d <= 30:
            r.error(where, "duration must be 1.5–30 seconds")
            continue
        total += d
        props = s.get("props") or {}
        spec = KINDS[kind]
        for req in spec["req"]:
            if props.get(req) in (None, "", []):
                r.error(where, f"props.{req} is required for kind '{kind}'")
        for key, limit in spec["text"].items():
            v = props.get(key)
            if isinstance(v, str) and len(v) > limit:
                r.error(where, f"props.{key} is {len(v)} chars; the {kind} layout holds {limit}")
        for key, (lo, hi) in spec["lists"].items():
            v = props.get(key)
            if v is not None and not (isinstance(v, list) and lo <= len(v) <= hi):
                r.error(where, f"props.{key} must be a list of {lo}–{hi} items")
        for path, text in _texts(props):
            if len(text) > 120:
                r.error(where, f"props.{path} is {len(text)} chars; keep on-screen text short")
        if kind == "screen":
            if props.get("device", "browser") not in DEVICES:
                r.error(where, f"device must be one of {', '.join(sorted(DEVICES))}")
            if props.get("camera", "push") not in CAMERAS:
                r.error(where, f"camera must be one of {', '.join(sorted(CAMERAS))}")
        if kind == "montage" and props.get("layout", "orbit") not in ("orbit", "stack", "grid", "row"):
            r.error(where, "layout must be orbit, stack, grid or row")
        if kind == "compare":
            for side in ("left", "right"):
                v = props.get(side) or {}
                if not isinstance(v, dict) or not v.get("title") or not (1 <= len(v.get("items", [])) <= 5):
                    r.error(where, f"props.{side} needs a title and 1–5 items")
        for ref in _media_refs(props):
            p = ws.assets / ref
            if Path(ref).suffix.lower() not in MEDIA_EXT:
                r.error(where, f"unsupported media '{ref}' (use {', '.join(sorted(MEDIA_EXT))})")
            elif not p.is_file():
                r.error(where, f"missing asset '{ref}' (expected at {p})")
        tr = s.get("transition") or {}
        ttype = tr.get("type", "none" if i == 0 else "fade")
        if ttype not in TRANSITIONS:
            r.error(where, f"unknown transition '{ttype}'")
        tdur = float(tr.get("duration", 0.5))
        if i > 0 and ttype not in ("none", "cut"):
            prev = scenes[i - 1].get("duration") or 0
            if tdur > min(d, prev) / 2:
                r.error(where, "transition is longer than half of an adjoining scene")

        cited = [str(c).upper() for c in s.get("claims", [])]
        for c in cited:
            if c not in claims:
                r.error(where, f"claim {c} is not in product-brief.md FACTUAL CLAIMS")
        visible = " ".join(t for _, t in _texts(props))
        n_text = s.get("narration")
        n_text = n_text.get("text") if isinstance(n_text, dict) else n_text
        if (_NUM.search(visible) or (n_text and _NUM.search(n_text))) and not cited:
            r.error(where, "shows or says a number without citing a claim id (numbers need sources)")
        if kind == "metric" and not cited:
            r.error(where, "a metric scene must cite the claim that backs the number")
        if n_text:
            offset = float(s["narration"].get("offset", 0.4)) if isinstance(s["narration"], dict) else 0.4
            need = len(n_text.split()) / SPEECH_WPS
            if need > d - offset + 0.6:
                r.error(where, f"narration needs ~{need:.1f}s but only {d - offset:.1f}s remain in the scene")
        for c in s.get("sfx", []) or []:
            if c.get("fx") not in sound.LIBRARY:
                r.error(where, f"unknown sound effect '{c.get('fx')}' (known: {', '.join(sound.LIBRARY)})")
            elif not 0 <= float(c.get("at", -1)) <= d:
                r.error(where, f"sfx '{c['fx']}' at {c.get('at')}s is outside the scene")

    lo, hi = cfg["duration"]["min"], cfg["duration"]["max"]
    if not lo <= total <= hi:
        r.error("timeline", f"total runtime {total:.1f}s is outside the configured {lo}–{hi}s")
    lines = sum(1 for s in scenes if s.get("narration"))
    if narr.get("enabled", True) and lines < 3:
        r.error("timeline.narration", f"narration is enabled but only {lines} scene(s) have a line")
    if narr.get("enabled", True) and lines > len(scenes) * 0.85:
        r.warn("timeline.narration", "narration on almost every scene; the framework asks for sparse lines")
    if scenes[0].get("kind") not in ("hook", "wordzoom", "statement", "screen", "terminal"):
        r.warn("timeline", "the film opens without a hook")
    if scenes[-1].get("kind") != "lockup":
        r.warn("timeline", "the film does not end on a lockup")
    return r


STYLE_PRESETS = {
    "graphite": {"ground": "#0B0C0F", "ground2": "#16181D", "ink": "#F4F1EA", "inkSoft": "#9A9DA6",
                 "accent": "#6E9BFF", "line": "#2A2D35", "dark": True},
    "midnight": {"ground": "#070A14", "ground2": "#101629", "ink": "#EEF1FA", "inkSoft": "#8F97AE",
                 "accent": "#8B7CFF", "line": "#222A40", "dark": True},
    "paper": {"ground": "#F6F4EF", "ground2": "#ECE9E1", "ink": "#16171A", "inkSoft": "#6B6E76",
              "accent": "#2F5BFF", "line": "#D9D5CB", "dark": False},
}


def resolve_style(tl_style: dict, cfg: dict) -> dict:
    preset = tl_style.get("preset", cfg["style"]["preset"])
    out = dict(STYLE_PRESETS[preset], preset=preset)
    if cfg["style"].get("accent"):
        out["accent"] = cfg["style"]["accent"]
    for k in ("accent", "ground", "ink"):
        if tl_style.get(k):
            out[k] = tl_style[k]
    out["fontHead"] = tl_style.get("fontHead", "Inter")
    return out


def compile_timeline(ws: Workspace) -> tuple[dict, Report]:
    cfg = ws.config()
    if not ws.timeline.exists():
        raise PromoError("timeline.json does not exist yet", hint="write it from creative-prompt.md (see docs/timeline.md)")
    tl = read_json(ws.timeline)
    claims = parse_claims(ws.brief.read_text()) if ws.brief.exists() else {}
    if not claims:
        raise PromoError("product-brief.md has no FACTUAL CLAIMS; the timeline cannot be fact-checked")
    rep = validate(tl, ws, cfg, claims)
    if not rep.ok:
        return {}, rep

    fps = int(cfg["format"]["fps"])
    scenes_out, cues, narration = [], [], []
    start = 0.0
    for i, s in enumerate(tl["scenes"]):
        d = float(s["duration"])
        props = dict(s.get("props") or {})
        where = f"scene '{s['id']}'"
        props["_t"] = _schedule(s["kind"], props, d, where, rep)
        refs = _media_refs(props)
        if refs:
            props["_media"] = {ref: media_aspect(ws.assets / ref) for ref in refs}
        tr = s.get("transition") or {}
        ttype = tr.get("type", "none" if i == 0 else "fade")
        tframes = 0 if ttype in ("none", "cut") or i == 0 else round(float(tr.get("duration", 0.5)) * fps)
        scenes_out.append({
            "id": s["id"], "kind": s["kind"], "purpose": s["purpose"], "source": s.get("source"),
            "from": round(start * fps), "durationInFrames": round(d * fps),
            "transition": {"type": ttype if i else "none", "frames": tframes},
            "props": props, "claims": s.get("claims", []),
        })
        if i > 0:
            cues += sound.transition_cues(ttype, start, s["id"])
        if s.get("autoSfx", True):
            cues += sound.scene_cues({"kind": s["kind"], "id": s["id"], "props": props}, start)
        for c in s.get("sfx", []) or []:
            cues.append(sound.cue(c["fx"], start + float(c["at"]), c.get("vol"), s["id"], "authored"))
        n = s.get("narration")
        if n:
            text = n["text"] if isinstance(n, dict) else n
            offset = float(n.get("offset", 0.4)) if isinstance(n, dict) else 0.4
            narration.append({"at": round(start + offset, 3), "text": text, "scene": s["id"],
                              "windowEnd": round(start + d + 0.4, 3)})
        start += d
    if not rep.ok:
        return {}, rep
    # Windows end where the next line starts, so lines never overlap.
    for a, b in zip(narration, narration[1:]):
        a["windowEnd"] = min(a["windowEnd"], b["at"] - 0.15)
    total_frames = round(start * fps)
    cues = sorted((c for c in cues if c["at"] < start - 0.05), key=lambda c: (c["at"], c["fx"]))
    quality = QUALITY[cfg["render"]["quality"]]
    rc = {
        "version": 1,
        "product": tl.get("product") or cfg["product"]["name"],
        "source": tl["source"],
        "seed": int(tl.get("seed", cfg["seed"])),
        "fps": fps,
        "durationInFrames": total_frames,
        "duration": round(start, 3),
        "compositions": [{"aspect": a, **ASPECTS[a]} for a in cfg["format"]["aspects"]],
        "quality": {"name": cfg["render"]["quality"], **quality},
        "style": resolve_style(tl.get("style", {}), cfg),
        "scenes": scenes_out,
        "narration": {"enabled": tl.get("narration", {}).get("enabled", True),
                      "reason": tl.get("narration", {}).get("reason"), "lines": narration},
        "sound": {"cues": cues, "ambience": bool(cfg["sound"].get("ambience"))},
        "audio": {"src": None},
    }
    write_json(ws.render_config, rc)
    ws.storyboard.write_text(storyboard_md(rc, cues))
    ws.narration.write_text("".join(f"[{fmt_time(n['at'])}] {n['text']}\n" for n in narration)
                            or f"(no narration: {rc['narration']['reason']})\n")
    return rc, rep


def _visual(scene: dict) -> str:
    p, k = scene["props"], scene["kind"]
    if k == "hook":
        return f"light + {len(p.get('fragments', []))} fragments → freeze → “{p['line']}”"
    if k == "title":
        return f"“{p['name']}”" + (f" / {p['tagline']}" if p.get("tagline") else "")
    if k == "statement":
        return f"“{p['text']}”"
    if k == "pillars":
        return " · ".join(i["title"] if isinstance(i, dict) else str(i) for i in p["items"])
    if k == "screen":
        return f"{p.get('device', 'browser')} · {p['media']} · camera {p.get('camera', 'push')} · {len(p.get('callouts', []))} callouts"
    if k == "flow":
        return " → ".join(st["label"] for st in p["steps"])
    if k == "terminal":
        return f"{len(p['lines'])} terminal lines"
    if k == "document":
        return f"document “{p['title']}” · {len(p['sections'])} sections"
    if k == "montage":
        return f"{len(p['items'])} items, {p.get('layout', 'orbit')}"
    if k == "compare":
        return f"{p['left']['title']} vs {p['right']['title']}"
    if k == "metric":
        return f"{p.get('prefix', '')}{p['value']}{p.get('suffix', '')} {p['label']}"
    if k == "lockup":
        return f"{p['name']}" + (f" — {p['line']}" if p.get("line") else "")
    return k


def storyboard_md(rc: dict, cues: list[dict]) -> str:
    fps = rc["fps"]
    lines = [f"# Storyboard — {rc['product']}", "",
             f"Generated from timeline.json by `promo compile`. {rc['duration']:.1f}s · {fps} fps · "
             f"source: {rc['source']} · style: {rc['style']['preset']} · seed {rc['seed']}", "",
             "| # | Time | Scene | Primitive | Purpose | Visual | In | Narration | Sound | Claims |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    by_scene: dict[str, list[str]] = {}
    for c in cues:
        by_scene.setdefault(c["scene"], []).append(c["fx"])
    narr = {n["scene"]: n["text"] for n in rc["narration"]["lines"]}
    for i, s in enumerate(rc["scenes"], 1):
        a = s["from"] / fps
        b = (s["from"] + s["durationInFrames"]) / fps
        fx = by_scene.get(s["id"], [])
        fx_s = ", ".join(sorted(set(fx), key=fx.index)) if fx else "—"
        lines.append(f"| {i} | {fmt_time(a)}–{fmt_time(b)} | {s['id']} | {s['kind']} | {s['purpose']} | "
                     f"{_visual(s)} | {s['transition']['type']} | {narr.get(s['id'], '—')} | {fx_s} | "
                     f"{', '.join(s['claims']) or '—'} |")
    lines += ["", "Background music: none. Sound is effects and voice only."]
    return "\n".join(lines) + "\n"
