"""PRODUCT_THEME_DISCOVERY: understand the real product before any storyboard exists.

Runs in both modes, after `init` and before `storyboard` / `compile` (which refuse to run
without it):

  1. confirm the target is the user's product, not this skill's own repository
  2. read the codebase (product-scan.json)
  3. launch and inspect the real web app (capture.inspect_web) and/or mobile app
     (mobile.inspect_mobile) where the environment allows, capturing genuine screens
  4. register screenshots already in the repository (supplied) and any illustrations, each
     under its true source
  5. select the strongest screens (screenshots.select)
  6. discover the product's theme from tokens, fonts, UI code, and the captured pixels
  7. write PRODUCT_ANALYSIS.md, THEME_ANALYSIS.md, THEME.json, ASSET_INVENTORY.md,
     SCREENSHOT_MANIFEST.json

Anything that could not be done is recorded with the stage that failed and why; nothing is
fabricated, and a blocked launch is never reported as an inspected app.
"""
from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from . import analyzer, capture, mobile, screenshots, theme
from .config import Workspace
from .screenshots import slug
from .util import PromoError, SKILL_DIR, read_json, scrub, write_json

STAGE = "PRODUCT_THEME_DISCOVERY"
SKILL_REPO = SKILL_DIR.parents[1]
WEB_FRAMEWORKS = {"Next.js", "React", "Vue", "Svelte", "SvelteKit", "Vite", "Astro", "Nuxt", "Angular", "Express",
                  "Fastify", "Hono", "Streamlit", "FastAPI", "Flask", "Django", "Remotion"}


def check_target(ws: Workspace) -> Path:
    cfg = ws.config()
    root = ws.product_root.resolve()
    if (root == SKILL_REPO or SKILL_DIR.resolve() in [root, *root.parents] or root in SKILL_DIR.resolve().parents) \
            and not cfg["product"].get("selfPromo"):
        raise PromoError(f"the product root {root} is the promo-video skill itself, not the user's product",
                         hint="run from the product's repository, or `promo init --product <path>`; to film this skill "
                              "on purpose set product.selfPromo: true")
    if not root.is_dir():
        raise PromoError(f"the product root {root} does not exist")
    return root


def static_routes(scan: dict, limit: int = 8) -> list[str]:
    routes = [r["route"] for r in scan.get("routes", []) if not re.search(r"[\[\]:*(]", r["route"])]
    routes = list(dict.fromkeys(["/"] + routes))

    def rank(r):
        return (0 if r == "/" else 1 if screenshots.HIGH.search(r) else 2 if screenshots.MEDIUM.search(r)
                else 4 if screenshots.LOW.search(r) else 3, r)
    return sorted(routes, key=rank)[:limit]


def product_names(cfg: dict, scan: dict) -> list[str]:
    names = [cfg["product"].get("name"), (scan.get("readme") or {}).get("title")]
    names += [m.get("name") for m in (scan.get("manifests") or {}).values()]
    return [n for n in dict.fromkeys(n for n in names if n)]


def readme_features(root: Path, scan: dict) -> list[str]:
    path = (scan.get("readme") or {}).get("path")
    if not path or not (root / path).is_file():
        return []
    text = (root / path).read_text(errors="replace")
    m = re.search(r"^#{1,3}\s*(features|what it does|highlights)\s*$(.*?)(?=^#{1,3}\s|\Z)", text, re.M | re.S | re.I)
    return [b.strip() for b in re.findall(r"^\s*[-*]\s+(.+)$", m.group(2), re.M)][:10] if m else []


def run(ws: Workspace, *, launch: bool = True, url: str | None = None, routes: list[str] | None = None,
        inspect_mobile: bool = True, size: str = "desktop", supplied: list[Path] | None = None,
        runner=mobile.default_run, chrome: str | None = None, startup_timeout: float = 90) -> dict:
    root = check_target(ws)
    cfg = ws.config()
    scan = analyzer.scan(root, exclude=ws.root)
    write_json(ws.scan, scan)
    names = product_names(cfg, scan)
    name = names[0] if names else root.name
    old = screenshots.load(ws.screenshot_manifest)
    overrides = {s["id"]: s for s in old.get("screenshots", []) if s.get("override")}
    shots: list[dict] = []
    rejected: list[dict] = []

    def add(path: Path, **kw):
        sid = kw.pop("sid")
        try:
            e = screenshots.entry(ws.root, path, sid=sid, product=name, **kw)
        except PromoError as exc:
            rejected.append({"path": str(path.name), "reason": str(exc)})
            return
        if sid in overrides:
            e["override"] = overrides[sid]["override"]
            e["overrideReason"] = overrides[sid].get("overrideReason")
        shots.append(e)

    frameworks = set(scan.get("frameworks") or [])
    plan = scan.get("launch") or {}
    is_web = bool(url or plan.get("url") or frameworks & WEB_FRAMEWORKS)
    platforms = mobile.detect_platforms(root)
    web = {"status": "not-applicable", "limitations": []}
    if is_web and not any(p["platform"] in ("flutter", "react-native") for p in platforms) or url:
        if launch or url:
            web = capture.inspect_web(ws, product_root=root, plan=plan, url=url, routes=routes or static_routes(scan),
                                      names=names, size=size, launch=launch, chrome=chrome,
                                      startup_timeout=startup_timeout)
        else:
            web = {"status": "skipped", "limitations": ["launching the web app was not requested (--no-launch)"],
                   "routes": [], "shots": []}
        for s in web.get("shots", []):
            row = next((r for r in web["routes"] if r["route"] == s["route"]), {})
            lim = [] if s["finding"] == "renders" else [s["finding"]]
            add(s["path"], sid=f"web-{slug(s['route'])}", platform="web", screen=s["title"] or s["route"],
                route=s["route"], source="captured", state=row.get("finding"), limitations=lim,
                feature=None)
    mob = {"status": "not-applicable", "limitations": []}
    if platforms and inspect_mobile:
        if launch:
            mob = mobile.inspect_mobile(ws, product_root=root, platforms=platforms, run=runner)
        else:
            mob = {"status": "skipped", "platform": platforms[0]["platform"], "shots": [],
                   "limitations": ["launching the mobile app was not requested (--no-launch)"]}
        for s in mob.get("shots", []):
            add(s["path"], sid=f"{(mob.get('device') or {}).get('platform', 'mobile')}-{slug(s['screen'])}",
                platform=(mob.get("device") or {}).get("platform", mob.get("platform") or "mobile"),
                screen=s["screen"], route=s.get("route"), source="captured", state="renders")
    # Screenshots already in the repository (or handed over by the user) are genuine but not captured here.
    repo_shots = [root / a["path"] for a in (scan.get("assets") or {}).get("screenshots", [])]
    for src in repo_shots + [Path(p) for p in (supplied or [])]:
        if not src.is_file():
            rejected.append({"path": src.name, "reason": "file not found"})
            continue
        dest = ws.assets / "supplied" / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dest)
        add(dest, sid=f"supplied-{slug(src.stem)}", platform="unknown", screen=src.stem, source="supplied",
            limitations=["supplied, not captured from the running product here"])
    for ill in sorted((ws.assets / "illustrations").glob("*")) if (ws.assets / "illustrations").is_dir() else []:
        if ill.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            add(ill, sid=f"illustration-{slug(ill.stem)}", platform="illustration", screen=ill.stem,
                source="illustration", limitations=["illustration made for the film; not a real screen"])
    manifest = {"version": 1, "stage": STAGE, "completedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "product": name, "web": _summary(web), "mobile": _summary(mob),
                "screenshots": shots, "rejected": rejected}
    screenshots.select(manifest, ws.root)
    approved = [ws.root / s["path"] for s in shots if s["approved"] and s["source"] == "captured"] or \
               [ws.root / s["path"] for s in shots if s["approved"]]
    th = theme.discover(root, scan, approved)
    th["product"] = name
    th["discoveredFrom"] = {"codebase": True, "screens": len(approved),
                            "screensSource": "captured" if any(s["source"] == "captured" and s["approved"] for s in shots)
                            else ("supplied" if approved else "none")}
    old_theme = read_json(ws.theme) if ws.theme.exists() else {}
    th["motion"] = old_theme.get("motion")
    write_json(ws.theme, th)
    screenshots.save(ws.screenshot_manifest, manifest)
    ws.theme_analysis.write_text(theme_md(th))
    ws.product_analysis.write_text(product_md(ws, root, scan, manifest, web, mob, th))
    ws.asset_inventory.write_text(inventory_md(ws, scan, manifest))
    return {"manifest": manifest, "theme": th, "web": web, "mobile": mob}


def _summary(rep: dict) -> dict:
    out = {"status": rep.get("status"), "stage": rep.get("stage"),
           "limitations": [scrub(x) for x in rep.get("limitations", [])]}
    for k in ("launch", "device", "platform", "url", "devicesSeen"):
        if rep.get(k):
            out[k] = rep[k]
    if rep.get("routes"):
        out["routes"] = [{k: (scrub(v) if isinstance(v, str) else v) for k, v in r.items() if k not in ("shot",)}
                         for r in rep["routes"]]
    if rep.get("screens"):
        out["screens"] = rep["screens"]
    return out


def done(ws: Workspace) -> bool:
    if not (ws.theme.exists() and ws.screenshot_manifest.exists()):
        return False
    return read_json(ws.screenshot_manifest).get("stage") == STAGE


def require(ws: Workspace, step: str) -> None:
    if not done(ws):
        raise PromoError(f"`{step}` needs the product-theme discovery stage first",
                         hint="run `promo discover` (it inspects the codebase, launches the app where possible, "
                              "captures real screens and reads the theme)")


# ── reports ────────────────────────────────────────────────────────────────────────

def _c(entry: dict | None) -> str:
    if not entry:
        return "unknown"
    tag = "verified" if entry.get("verified") else "estimated"
    return f"`{entry['value']}` ({tag}; {entry.get('token') or ''} {entry['source']})".replace("( ", "(")


def theme_md(th: dict) -> str:
    o, p, f, ui = th["original"], th["promo"], th["typography"], th["ui"]
    L = [f"# THEME ANALYSIS — {th.get('product')}", "",
         "Discovered from the product's code" + (f" and {th['discoveredFrom']['screens']} real screen(s) "
                                                 f"({th['discoveredFrom']['screensSource']})" if th["discoveredFrom"]["screens"] else
                                                 " only (no screen could be sampled)") + ". `verified` = read from a token or "
         "style rule; `estimated` = sampled from pixels. The machine-readable source of truth is `THEME.json`.", "",
         "## Colour palette", ""]
    if not o["modes"]:
        L.append("No colour tokens were found in the codebase.")
    for mode, pal in o["modes"].items():
        L += [f"### {mode.title()} mode" + (" (default, as the real screens show)" if mode == o["defaultMode"] else ""), "",
              "| Role | Value |", "|---|---|"]
        for role in ("primary", "secondary", "accent", "background", "surface", "text", "border",
                     "success", "warning", "error", "info"):
            L.append(f"| {role} | {_c(pal.get(role))} |")
        L.append("")
    L += [f"Dark mode: {'yes' if o['hasDarkMode'] else 'not defined in the code'} · gradients in the UI code: {o['gradients']}",
          f"Core roles with no evidence (left unknown, not invented): {', '.join(o['unknown']) or 'none'}; "
          "other roles marked unknown above were not found either.", ""]
    if o.get("corroboration"):
        L += ["Pixel corroboration:", ""] + [
            f"- {c['role']}: token {c['token']} vs sampled {c['sampled']} → {'agrees' if c['agrees'] else 'differs'} "
            f"(distance {c['distance']})" for c in o["corroboration"]] + [""]
    L += ["## Typography", "", "| Family | Uses | Source | Font file |", "|---|---|---|---|"]
    L += [f"| {x['family']} | {x['uses']} | {x['source']} | {x['file'] or 'not in the repository'} |" for x in f["families"]] \
        or ["| unknown | | | |"]
    cls = ui["tailwindClasses"]
    L += ["", f"Conventions seen: uppercase ×{ui['counts'].get('uppercase', 0) + cls.get('uppercase', 0)}, "
          f"letter-spacing ×{ui['counts'].get('tracking', 0) + sum(n for c, n in cls.items() if c.startswith('tracking'))}, "
          f"weights {', '.join(c for c in cls if c.startswith('font-')) or 'from CSS'}.", "",
          "## Interface language", "",
          f"- Corner radius: {ui['radius'] or 'unknown'} ({ui['evidence'].get('radius', 'utility classes')})",
          f"- Shadows ×{ui['counts'].get('shadow', 0) + sum(n for c, n in cls.items() if c.startswith('shadow'))}, "
          f"borders ×{ui['counts'].get('border', 0)}, backdrop blur ×{ui['counts'].get('blur', 0)}",
          f"- Motion: {', '.join(ui['motionLibraries']) or 'CSS only'} (transitions ×{ui['counts'].get('transition', 0)}, "
          f"animations ×{ui['counts'].get('animation', 0)})",
          f"- Icons: {', '.join(ui['iconLibraries']) or 'none detected'} · UI kits: {', '.join(ui['uiKits']) or 'none detected'}",
          "", "## Classification (descriptive, from evidence)", ""]
    L += [f"- **{c['label']}** — {c['evidence']}" for c in o["classification"]]
    L += ["", "## How the film uses it", "",
          f"Ground `{p['ground']}` · surface `{p['ground2']}` · ink `{p['ink']}` · accent `{p['accent']}` · "
          f"{'dark' if p['dark'] else 'light'} film · type {p['fontHead']}" + (f" (`{p['fontFile']}`)" if p["fontFile"] else ""), "",
          "Promotional additions that complement it: " + ", ".join(p["allowed"]) + ".", ""]
    L += [f"- {n}" for n in p["notes"]] or ["- No departures from the product's theme."]
    return "\n".join(L) + "\n"


def product_md(ws, root, scan, manifest, web, mob, th) -> str:
    readme = scan.get("readme") or {}
    feats = readme_features(root, scan)
    sel = [s for s in manifest["screenshots"] if s["selected"]]
    rendered = [r for r in web.get("routes", []) if r.get("finding") == "renders"]
    if web.get("status") == "captured" and len(rendered) >= 2:
        status = "functioning web application (it launched here and its routes render)"
    elif web.get("status") == "captured":
        status = "launches here; one screen renders (a landing page or an early prototype)"
    elif mob.get("status") == "captured":
        status = "functioning mobile application (it built, launched and was captured here)"
    elif web.get("status") == "blocked" or mob.get("status") == "blocked":
        status = "not verified running: the launch was blocked (see Limitations)"
    else:
        status = "not launched (inspection from the codebase only)"
    ctas = list(dict.fromkeys(c for r in web.get("routes", []) for c in (r.get("ctas") or [])))[:8]
    L = [f"# PRODUCT ANALYSIS — {manifest['product']}", "",
         f"Stage: {STAGE} · {manifest['completedAt']} · product root: `{Path(root).name}` (not the skill repository)", "",
         "## What it is", "",
         f"- Name: {manifest['product']}",
         f"- Purpose: {readme.get('intro') or next((m.get('description') for m in (scan.get('manifests') or {}).values() if m.get('description')), None) or 'not stated in the repository'}",
         f"- Stack: {scan.get('projectType')} · {', '.join(scan.get('frameworks') or []) or 'unknown'}",
         f"- State: {status}",
         "- Audience: " + ("see product-brief.md (only where the repository states it)"), "",
         "## Features (from the README)", ""]
    L += [f"- {f}" for f in feats] or ["- The README does not list features; derive them from the code in product-brief.md."]
    L += ["", "## Screens and journey", "", "| Screen | Route | Finding | Calls to action |", "|---|---|---|---|"]
    for r in web.get("routes", []):
        L.append(f"| {r.get('title') or r['route']} | `{r['route']}` | {scrub(r.get('finding', ''))} | "
                 f"{', '.join(r.get('ctas') or []) or '—'} |")
    for s in mob.get("screens", []):
        L.append(f"| {s['screen']} | `{s['route']}` | {s['finding']} | — |")
    if not web.get("routes") and not mob.get("screens"):
        L.append("| — | — | no live screen was inspected | — |")
    L += ["", f"Primary calls to action seen on screen: {', '.join(ctas) or 'none observed'}", "",
          "## Theme", "", f"{', '.join(c['label'] for c in th['original']['classification'])}; default "
          f"{th['original']['defaultMode']} mode" + (", dark mode defined" if th["original"]["hasDarkMode"] else "")
          + f". Details: THEME_ANALYSIS.md.", "", "## Strongest visuals (selected screenshots)", ""]
    L += [f"- `{s['id']}` — {s['screen']} ({s['source']}, {s['width']}×{s['height']}): {s['reason']}" for s in sel] \
        or ["- **No genuine product screenshots are available.** The film can only use real material that exists "
            "(e.g. the product's text, code output, logo); it must not show invented UI."]
    lim = web.get("limitations", []) + mob.get("limitations", [])
    L += ["", "## Limitations and blocked workflows", ""]
    L += [f"- {scrub(x)}" for x in lim] or ["- none"]
    if web.get("stage") or mob.get("stage"):
        L.append(f"- Blocked at: {', '.join(x for x in (web.get('stage'), mob.get('stage')) if x)}")
    return "\n".join(L) + "\n"


def inventory_md(ws, scan, manifest) -> str:
    a = scan.get("assets") or {}
    L = [f"# ASSET INVENTORY — {manifest['product']}", "", "## Screenshots", "",
         "| ID | Source | Platform | Screen | Size | Selected | Reason |", "|---|---|---|---|---|---|---|"]
    for s in sorted(manifest["screenshots"], key=lambda x: (not x["selected"], -(x["score"] or 0))):
        L.append(f"| `{s['id']}` | {s['source']} | {s['platform']} | {s['screen']} | {s['width']}×{s['height']} | "
                 f"{'yes' if s['selected'] else 'no'} | {s['reason']} |")
    if manifest.get("rejected"):
        L += ["", "Rejected files: " + "; ".join(f"{r['path']} ({r['reason']})" for r in manifest["rejected"])]
    L += ["", "## Brand assets in the repository", "",
          f"- Logos: {', '.join(x['path'] for x in a.get('logos', [])[:8]) or 'none found'}",
          f"- Fonts: {', '.join(a.get('fonts', [])[:8]) or 'none found'}",
          f"- Videos: {', '.join(x['path'] for x in a.get('videos', [])[:5]) or 'none'}",
          f"- Other images: {len(a.get('images', []))}", "",
          "Genuine screens live in `assets/captured/` (taken here) and `assets/supplied/` (from the repository or "
          "the user). Illustrations live in `assets/illustrations/` and are never shown as real screens."]
    return "\n".join(L) + "\n"
