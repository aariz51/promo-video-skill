"""Build the three verification films at final quality, end to end through the CLI.

    python3 examples/verification/build.py

Every film starts with `promo discover` against a real, running product:

  autonomous         Mode A · the Tallyboard web app (Node), launched and captured · voice-over
                     (macOS `say`, keyless) + effects · 1920×1080 and 886×1920
  reference          Mode B · the same web app on the synthetic `slow` reference (dark colour
                     fields; dissolve, wipe, dip) · effects only · 1920×1080
  autonomous-mobile  Mode A · a real Flutter iOS app built and captured on promo's own simulator
                     · effects only · 1080×1920 (skipped, and said so, without Flutter / Xcode)

The agent's creative work (brief, creative prompt, direction text, scene content) comes from
the test fixtures, standing in for what the agent writes; everything else is the real
pipeline. Generated: `tallyboard/` (fixture web app), `tallyboard-app/` (fixture Flutter app), `reference.mp4`, and each workspace's
`out/`, `build/` and `deliver/` (git-ignored). The text artifacts and reports are committed.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import films  # noqa: E402
import helpers  # noqa: E402
from test_direction import fill_direction, fill_timeline  # noqa: E402

from promo_engine import direction  # noqa: E402
from promo_engine.cli import main  # noqa: E402
from promo_engine.config import Workspace  # noqa: E402
from promo_engine.util import read_json, write_json  # noqa: E402


def run(*args: str) -> None:
    code = main([str(a) for a in args])
    if code:
        sys.exit(f"`promo {' '.join(map(str, args))}` failed with exit {code}")


def product() -> Path:
    prod = HERE / "tallyboard"
    if prod.exists():
        shutil.rmtree(prod)
    return helpers.make_web_product(prod, helpers.free_port())


def stage_assets(ws: Workspace, prod: Path) -> None:
    ws.brief.write_text(helpers.BRIEF)
    (ws.assets / "screenshots").mkdir(parents=True, exist_ok=True)
    shutil.copy(prod / "public" / "screenshots" / "dashboard.png", ws.assets / "screenshots" / "dashboard.png")


def autonomous(prod: Path) -> Workspace:
    ws = Workspace.at(HERE / "autonomous")
    w = ["-w", ws.root]
    provider = "say" if shutil.which("say") else "files"
    run(*w, "init", "--product", prod, "--name", "Tallyboard", "--reference", "none", "--audio", "voiceover",
        "--provider", provider, "--formats", "16:9", "store-portrait", "--runtime", "10-20")
    stage_assets(ws, prod)
    run(*w, "discover", "--no-mobile")
    run(*w, "check", "brief")
    if ws.creative.exists():
        ws.creative.unlink()
    run(*w, "adapt")
    ws.creative.write_text(films.complete_creative_prompt(ws.creative.read_text()))
    run(*w, "check", "creative")
    ws.timeline.write_text(json.dumps(films.with_real_screen(films.COMPACT, "web-reports"), indent=2))
    run(*w, "check", "timeline")
    run(*w, "build")  # final quality
    run(*w, "deliver")
    return ws


def reference_driven(prod: Path) -> Workspace:
    ref = HERE / "reference.mp4"
    helpers.make_reference(ref, "slow")
    ws = Workspace.at(HERE / "reference")
    w = ["-w", ws.root]
    run(*w, "init", "--product", prod, "--name", "Tallyboard", "--reference", ref, "--audio", "effects",
        "--formats", "16:9")
    stage_assets(ws, prod)
    run(*w, "discover", "--no-mobile")
    run(*w, "watch", "--no-whisper", "--refresh")
    run(*w, "direction", "--force")
    ws.direction.write_text(fill_direction(ws.direction.read_text(), direction.load_breakdown(ws)))
    run(*w, "check", "direction")
    run(*w, "storyboard", "--force")
    write_json(ws.timeline, fill_timeline(read_json(ws.timeline)))
    run(*w, "check", "timeline")
    run(*w, "build")
    run(*w, "deliver")
    return ws


def autonomous_mobile() -> Workspace | None:
    if not (shutil.which("flutter") and shutil.which("xcrun")):
        print("autonomous-mobile: skipped (needs Flutter and Xcode simulators)")
        return None
    app = HERE / "tallyboard-app"
    if app.exists():
        shutil.rmtree(app)
    root = helpers.make_flutter_product(app)
    ws = Workspace.at(HERE / "autonomous-mobile")
    w = ["-w", ws.root]
    run(*w, "init", "--product", root, "--name", "Tallyboard", "--reference", "none", "--audio", "effects",
        "--formats", "9:16", "--runtime", "10-20")
    main_dart = (root / "lib" / "main.dart").read_text().splitlines()
    line = lambda needle: next(i for i, t in enumerate(main_dart, 1) if needle in t)  # noqa: E731
    history = "'/history'"
    brief = helpers.BRIEF.split("## FACTUAL CLAIMS")[0] + (
        "## FACTUAL CLAIMS\n\n"
        f"- C1: Totals are grouped by category — source: lib/main.dart:{line('Travel · Food')}\n"
        f"- C2: The month exports as CSV — source: lib/main.dart:{line('Export CSV')}\n"
        f"- C3: Past months stay in a history — source: lib/main.dart:{line(history)}\n\n"
        "## RESTRICTIONS\n\nDemo data only; no real receipts.\n")
    ws.brief.write_text(brief)
    run(*w, "check", "brief")
    run(*w, "discover")
    tl = films.with_real_screen(films.COMPACT, "ios-result")
    next(s for s in tl["scenes"] if s["kind"] == "screen")["props"]["device"] = "phone"
    ws.timeline.write_text(json.dumps(tl, indent=2))
    run(*w, "check", "timeline")
    run(*w, "build")
    run(*w, "deliver")
    return ws


if __name__ == "__main__":
    p = product()
    for ws in (autonomous(p), reference_driven(p), autonomous_mobile()):
        if ws is None:
            continue
        val = read_json(ws.qa_dir / "validation.json")
        print(f"{ws.root.name}: QA {val['result']} · " + ", ".join(
            f"{a} {v['width']}×{v['height']} {v['duration']}s" for a, v in val["videos"].items()))
