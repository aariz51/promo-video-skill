"""Layer 7: VIDEO RENDERER.

One Remotion project (skills/promo-video/renderer) renders every product. Nothing is
copied into the product repo: `render-config.json` goes in as input props and a staged
public folder (fonts + the product's assets + the audio master) goes in as --public-dir.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .config import ASPECTS, QUALITY, Workspace, render_scale
from .timeline import _media_refs
from .util import FONTS_DIR, RENDERER_DIR, PromoError, free_gb, read_json, require_tools, write_json

MIN_FREE_GB = {"draft": 0.8, "final": 1.5}


def ensure_renderer() -> None:
    require_tools("node", "npx")
    if not (RENDERER_DIR / "node_modules" / "@remotion" / "cli").is_dir():
        print("Installing renderer dependencies (one time)…")
        res = subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=RENDERER_DIR,
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise PromoError("could not install the renderer's dependencies:\n  "
                             + "\n  ".join(res.stderr.strip().splitlines()[-6:]),
                             hint=f"run `npm ci` in {RENDERER_DIR} and check your network / Node version (>= 18)")


def stage(ws: Workspace, rc: dict) -> Path:
    """Build the public dir the renderer sees and the props file it reads."""
    pub = ws.stage
    (pub / "fonts").mkdir(parents=True, exist_ok=True)
    for f in FONTS_DIR.iterdir():
        dst = pub / "fonts" / f.name
        if f.is_file() and (not dst.exists() or dst.stat().st_size != f.stat().st_size):
            shutil.copy2(f, dst)
    font = rc.get("style", {}).get("fontSource")
    if font:
        src = ws.product_root / font
        if src.is_file():
            shutil.copy2(src, pub / rc["style"]["fontFile"])
        else:
            raise PromoError(f"the product's font {font} (THEME.json) is missing", hint="re-run `promo discover`")
    missing = []
    for s in rc["scenes"]:
        for ref in _media_refs(s["props"]):
            src = ws.assets / ref
            if not src.is_file():
                missing.append(f"{s['id']}: {ref}")
                continue
            dst = pub / "assets" / ref
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                shutil.copy2(src, dst)
    if missing:
        raise PromoError("assets referenced by the timeline are missing:\n  " + "\n  ".join(missing),
                         hint="add them under promo/assets/ or change the scenes, then `promo compile`")
    props = dict(rc)
    silent = (rc.get("audioPolicy") or {}).get("mode") == "silent"
    if not silent and not ws.master_audio.is_file():
        raise PromoError("the audio mode has sound but there is no audio master", hint="run `promo audio` first")
    # Silent films never reference audio, so nothing stale on disk can be attached.
    props["audio"] = {"src": None if silent else "audio/master.wav"}
    write_json(ws.root / "build" / "render-props.json", props)
    return pub


def render(ws: Workspace, aspect: str, *, quality: str | None = None) -> Path:
    if aspect not in ASPECTS:
        raise PromoError(f"unsupported aspect '{aspect}'")
    rc = read_json(ws.render_config)
    cfg = ws.config()
    quality = quality or cfg["render"]["quality"]
    q = QUALITY[quality]
    ensure_renderer()
    need = MIN_FREE_GB[quality]
    if free_gb(ws.root) < need:
        raise PromoError(f"only {free_gb(ws.root):.1f} GB free; rendering needs about {need} GB",
                         hint="free disk space and re-run `promo render`")
    stage(ws, rc)
    out_dir = ws.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    comp = ASPECTS[aspect]
    suffix = aspect.replace(":", "x")
    out = out_dir / f"promo-{suffix}{'-draft' if quality == 'draft' else ''}.mp4"
    cmd = ["npx", "remotion", "render", "src/index.ts", comp["id"], str(out),
           f"--props={ws.root / 'build' / 'render-props.json'}", f"--public-dir={ws.stage}",
           f"--crf={q['crf']}", f"--scale={render_scale(aspect, quality)}", "--log=error"]
    if (rc.get("audioPolicy") or {}).get("mode") == "silent":
        cmd.append("--muted")  # no audio stream at all, rather than a silent one
    log = ws.root / "build" / f"render-{suffix}.log"
    print(f"Rendering {comp['id']} ({comp['width']}×{comp['height']}, {quality}) → {out}")
    res = subprocess.run(cmd, cwd=RENDERER_DIR, capture_output=True, text=True)
    log.write_text((res.stdout or "") + "\n" + (res.stderr or ""))
    if res.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
        tail = "\n  ".join(((res.stderr or "") + (res.stdout or "")).strip().splitlines()[-10:])
        raise PromoError(f"render failed for {aspect}:\n  {tail}", hint=f"full log: {log}")
    return out


def stills(ws: Workspace, aspect: str, *, scenes: list[str] | None = None, at: float = 0.85,
           scale: float = 0.5) -> list[Path]:
    """Single frames from any aspect without a full render: one per scene, at `at` of it.

    Bundles once, then renders each frame from the bundle. Used to review 9:16 and 1:1
    layouts cheaply, and to produce real stills of the film for use as media.
    """
    if aspect not in ASPECTS:
        raise PromoError(f"unsupported aspect '{aspect}'")
    rc = read_json(ws.render_config)
    ensure_renderer()
    stage(ws, rc)
    bundle = ws.root / "build" / "bundle"
    res = subprocess.run(["npx", "remotion", "bundle", "src/index.ts", f"--out-dir={bundle}",
                          f"--public-dir={ws.stage}", "--log=error"], cwd=RENDERER_DIR, capture_output=True, text=True)
    if res.returncode != 0:
        raise PromoError("could not bundle the renderer:\n  " + "\n  ".join(res.stderr.strip().splitlines()[-8:]))
    comp = ASPECTS[aspect]
    out_dir = ws.qa_dir / "stills" / aspect.replace(":", "x")
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(scenes or [s["id"] for s in rc["scenes"]])
    unknown = wanted - {s["id"] for s in rc["scenes"]}
    if unknown:
        raise PromoError(f"no scene with id {', '.join(sorted(unknown))}")
    out = []
    for i, s in enumerate(rc["scenes"], 1):
        if s["id"] not in wanted:
            continue
        frame = s["from"] + int(s["durationInFrames"] * at)
        dest = out_dir / f"{i:02d}-{s['id']}.png"
        res = subprocess.run(["npx", "remotion", "still", str(bundle), comp["id"], str(dest), f"--frame={frame}",
                              f"--props={ws.root / 'build' / 'render-props.json'}", f"--scale={scale}", "--log=error"],
                             cwd=RENDERER_DIR, capture_output=True, text=True)
        if res.returncode != 0 or not dest.is_file():
            raise PromoError(f"could not render a still of '{s['id']}' at {aspect}:\n  "
                             + "\n  ".join(res.stderr.strip().splitlines()[-8:]))
        out.append(dest)
    return out
