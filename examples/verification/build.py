"""Build the two verification films at final quality, end to end through the CLI.

    python3 examples/verification/build.py

Mode A (autonomous): the Tallyboard fixture product, voice-over (macOS `say`, keyless) +
effects, 1920×1080 and 886×1920. Mode B (reference-driven): the same product rebuilt on the
synthetic `slow` reference (dissolve, wipe, dip), effects only, 1920×1080.

The agent's creative work (brief, creative prompt, direction text, scene content) comes from
the test fixtures, standing in for what the agent writes; everything else is the real
pipeline. Generated: `tallyboard/` (fixture product), `reference.mp4`, and each workspace's
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
    return helpers.make_product(prod)


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
    run(*w, "scan")
    run(*w, "check", "brief")
    if ws.creative.exists():
        ws.creative.unlink()
    run(*w, "adapt")
    ws.creative.write_text(films.complete_creative_prompt(ws.creative.read_text()))
    run(*w, "check", "creative")
    ws.timeline.write_text(json.dumps(films.COMPACT, indent=2))
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
    run(*w, "scan")
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


if __name__ == "__main__":
    p = product()
    for ws in (autonomous(p), reference_driven(p)):
        val = read_json(ws.qa_dir / "validation.json")
        print(f"{ws.root.name}: QA {val['result']} · " + ", ".join(
            f"{a} {v['width']}×{v['height']} {v['duration']}s" for a, v in val["videos"].items()))
