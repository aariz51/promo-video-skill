"""Fixtures: a small fictional product repo and a complete, valid promo workspace.

Everything is generated at test time with the standard library, so the repository holds
no binary fixtures and no real product's material.
"""
from __future__ import annotations

import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "promo-video"
sys.path.insert(0, str(SKILL / "engine"))

from promo_engine.config import Workspace, init_workspace  # noqa: E402


def png(path: Path, w: int, h: int, rgb=(40, 44, 60)) -> Path:
    """A solid-colour PNG with a lighter top band (so it is not blank)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(h):
        c = (rgb[0] + 60, rgb[1] + 60, rgb[2] + 80) if y < h // 8 else rgb
        rows.append(b"\x00" + bytes(c) * w)
    raw = zlib.compress(b"".join(rows), 6)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", raw) + chunk(b"IEND", b""))
    return path


def make_product(root: Path) -> Path:
    """Tallyboard: a fictional Next.js expense dashboard."""
    (root / "app" / "reports").mkdir(parents=True, exist_ok=True)
    (root / "styles").mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    (root / "package.json").write_text(json.dumps({
        "name": "tallyboard", "version": "1.2.0",
        "description": "Turns receipts into a categorised monthly expense report.",
        "scripts": {"dev": "next dev --port 3100", "build": "next build", "test": "vitest"},
        "dependencies": {"next": "15.0.0", "react": "19.0.0", "tailwindcss": "4.0.0"},
    }, indent=2))
    (root / "README.md").write_text(
        "# Tallyboard\n\nTallyboard turns a folder of receipts into a categorised monthly expense report.\n\n"
        "## Features\n\n- Drop receipts in; totals are grouped by category.\n- Export the month as CSV.\n"
        "- Everything runs locally; receipts never leave your machine.\n\n## Quick start\n\n```bash\nnpm install\nnpm run dev\n```\n")
    (root / "app" / "page.tsx").write_text("export default function Home() { return <main>Drop receipts</main>; }\n")
    (root / "app" / "reports" / "page.tsx").write_text("export default function Reports() { return <main>Report</main>; }\n")
    (root / "styles" / "globals.css").write_text(
        ":root { --brand: #1F8A70; --ink: #111418; --paper: #F7F5F0; }\nbody { font-family: 'Geist', sans-serif; color: #111418; }\n")
    (root / ".env.example").write_text("DATABASE_URL=\nEXPORT_BUCKET=\n")
    (root / ".env").write_text("SECRET_TOKEN=do-not-read-me\n")
    (root / "api key.txt").write_text("sk-fake-should-never-be-read\n")
    (root / "tests" / "report.test.ts").write_text("test('groups by category', () => {});\n")
    png(root / "public" / "logo.png", 64, 64, (31, 138, 112))
    png(root / "public" / "screenshots" / "dashboard.png", 320, 200)
    png(root / "public" / "screenshots" / "report.png", 320, 200, (30, 30, 40))
    return root


BRIEF = """# PRODUCT PROMO BRIEF

## PRODUCT

Tallyboard turns a folder of receipts into a categorised monthly expense report.

## TARGET USER

Freelancers and small teams who reconcile expenses monthly.

## CORE PROBLEM

Receipts pile up unsorted and the month-end report is manual.

## VALUE PROPOSITION

Receipts in, a finished report out. Carrying ideas: drop · group · export.

## HERO FEATURES

1. Category grouping (README.md)
2. CSV export (README.md)

## PRODUCT MOMENTS

- Dropping receipts on the home screen (app/page.tsx)
- The report view (app/reports/page.tsx)

## VISUAL ASSETS

- public/logo.png, public/screenshots/dashboard.png, public/screenshots/report.png
- Brand colour #1F8A70 (styles/globals.css)

## DEMO OPPORTUNITIES

Receipts → grouped categories → monthly report → CSV.

## FACTUAL CLAIMS

- C1: Totals are grouped by category — source: README.md:7
- C2: The month exports as CSV — source: README.md:8
- C3: Receipts never leave your machine — source: README.md:9
- C4: Version 1.2.0 — source: package.json:3

## RESTRICTIONS

No customer names, no accuracy percentages, no pricing.
"""

TRANSCRIPT = [
    {"t": 1.0, "text": "every great product starts with a single moment of clarity"},
    {"t": 6.0, "text": "we built the fastest way to understand your data"},
]


def inspiration_md(duration: float = 40.0) -> str:
    rules = "\n".join(f"{i}. R{i} — rule number {i} about pacing and light (evidence: 0:{i + 2:02d})" for i in range(1, 13))
    return f"""# YOUTUBE INSPIRATIONAL PROMPT

Source: https://www.youtube.com/watch?v=abcdefghijk

## 1. VIDEO IDENTITY

- Overall visual identity: dark, precise, one warm accent.
- Creative style: product-first minimalism.
- Emotional tone: calm confidence.
- Production character: studio motion design.
- Perceived production quality: high.
- Storytelling style: problem, then demonstration, then lockup.

## 2. HOOK ANALYSIS

- 0:00–0:05, what happens: a single line of light draws across black.
- Why the hook works structurally: it withholds the subject until 0:04.

## 3. STORY STRUCTURE

| Timestamp | Scene purpose | Visual concept | Subject | Composition | Camera | Animation | Typography | UI treatment | Transition out | Sound | Narration (role) | Emotional role |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0:00–0:06 | Hook | light line | line | centred | static | draw-on | none | none | light bloom | tone | none | curiosity |
| 0:06–0:14 | Problem | clutter | papers | scattered | push | drift | one line | none | match cut | rustle | states the pain | tension |
| 0:14–0:28 | Demonstration | product UI | app | centred device | push | UI reveal | labels | real UI | hard cut | clicks | explains step | relief |
| 0:28–0:40 | Lockup | logo | brand | centred | pull | settle | name | none | fade | resolve | tagline | resolve |

## 4. PACING ANALYSIS

- Average scene duration: 10 s; the demonstration runs longest (0:14–0:28).

## 5. MOTION LANGUAGE

Light as the connective tissue; every transition is a push into the next subject.

## 6. VISUAL LANGUAGE

- Color system: near-black with one amber accent.

## 7. SOUND LANGUAGE

- Silence: the first two seconds are silent.
- Music in the source (note only; the promo will not use background music): a soft pad.

## 8. NARRATION STRUCTURE

- Density: four short lines in forty seconds.

## 9. TYPOGRAPHY SYSTEM

- Headline size and hierarchy: one large sans line per scene.

## 10. SCENE TRANSITION SYSTEM

| At | From → To | Technique | Why it works |
|---|---|---|---|
| 0:06 | hook → problem | light bloom | resets the eye |

## 11. CINEMATIC ARC

HOOK (0:00–0:06) → PROBLEM (0:06–0:14) → DEMONSTRATION (0:14–0:28) → LOCKUP (0:28–0:40)

## 12. REUSABLE CREATIVE RULES

{rules}
"""


def timeline(media: str = "screenshots/dashboard.png") -> dict:
    return {
        "version": 1, "product": "Tallyboard", "source": "framework", "seed": 3,
        "style": {"preset": "graphite", "accent": "#1F8A70"},
        "narration": {"enabled": True},
        "scenes": [
            {"id": "hook", "kind": "hook", "duration": 8, "purpose": "mystery: receipts swirl",
             "props": {"line": "Where did this month go?", "fragments": ["taxi", "lunch", "hosting", "train"]},
             "narration": {"text": "Every month ends the same way.", "offset": 5.2}},
            {"id": "title", "kind": "title", "duration": 5, "purpose": "name", "transition": {"type": "light", "duration": 0.8},
             "props": {"name": "Tallyboard", "tagline": "Receipts in. A finished report out."}},
            {"id": "flow", "kind": "flow", "duration": 14, "purpose": "hero demonstration", "claims": ["C1"],
             "transition": {"type": "push", "duration": 0.6},
             "props": {"title": "From receipts to a report", "steps": [
                 {"label": "Drop receipts", "lines": ["taxi.jpg", "lunch.pdf"]},
                 {"label": "Grouped by category"}, {"label": "Monthly report"}]},
             "narration": "Drop the receipts in. Tallyboard groups every total by category."},
            {"id": "screen", "kind": "screen", "duration": 12, "purpose": "the real report view", "claims": ["C2"],
             "props": {"media": media, "device": "browser", "callouts": [{"x": 0.3, "y": 0.4, "label": "Export CSV"}],
                       "caption": "The month, ready to export."},
             "narration": "The month exports as a spreadsheet."},
            {"id": "trust", "kind": "statement", "duration": 9, "purpose": "trust", "claims": ["C3"],
             "props": {"text": "Your receipts never leave your machine.", "accent": ["never"]}},
            {"id": "compare", "kind": "compare", "duration": 8, "purpose": "two paths", "claims": ["C1", "C2"],
             "props": {"left": {"title": "By hand", "items": ["Sort receipts", "Type totals"]},
                       "right": {"title": "Tallyboard", "items": ["Grouped by category", "Export CSV"]}}},
            {"id": "lockup", "kind": "lockup", "duration": 8, "purpose": "close", "transition": {"type": "fade", "duration": 0.6},
             "props": {"name": "Tallyboard", "line": "Drop. Group. Export."},
             "narration": "Tallyboard. The month, sorted."},
        ],
    }


class Env:
    """A temp product + workspace, torn down after the test."""

    def __init__(self, *, inspiration: bool = False):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-test-"))
        self.product = make_product(self.tmp / "tallyboard")
        self.ws = Workspace.at(self.product / "promo")
        init_workspace(self.ws, product_root=self.product, name="Tallyboard",
                       inspiration_url="https://www.youtube.com/watch?v=abcdefghijk" if inspiration else None)
        cfg = json.loads(self.ws.config_path.read_text())
        cfg["duration"] = {"min": 30, "max": 100}
        self.ws.config_path.write_text(json.dumps(cfg))

    def with_artifacts(self, tl: dict | None = None) -> "Env":
        self.ws.brief.write_text(BRIEF)
        (self.ws.assets / "screenshots").mkdir(parents=True, exist_ok=True)
        shutil.copy(self.product / "public" / "screenshots" / "dashboard.png", self.ws.assets / "screenshots" / "dashboard.png")
        self.ws.timeline.write_text(json.dumps(tl or timeline(), indent=2))
        return self

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def fake_watch_script(dir: Path, *, fail: bool = False, video: Path | None = None) -> Path:
    """A stand-in for claude-video's watch.py that prints a report in the real format."""
    dir.mkdir(parents=True, exist_ok=True)
    script = dir / "watch.py"
    frames = "\n".join(f"- `{dir}/frames/f{i:03d}.jpg` (t=00:{i * 5:02d}, reason=scene-change)" for i in range(8))
    report = f"""
# watch: video report

- **Source:** SRC
- **Title:** A calm launch film
- **Duration:** 00:40 (40.0s)
- **Resolution:** 1280x720 (h264)
- **Detail:** balanced
- **Transcript:** captions

## Frames

Frames live at: `{dir}/frames`

{frames}

## Transcript

_Source: captions._

```
[00:01] every great product starts with a single moment of clarity
[00:06] we built the fastest way to understand your data
```

---
_Work dir: `{dir}` — delete when done._
"""
    body = "import sys, os, shutil\n"
    if fail:
        body += "sys.stderr.write('ERROR: [youtube] abcdefghijk: Video unavailable\\n'); sys.exit(1)\n"
    else:
        body += f"report = {report!r}\nprint(report.replace('SRC', sys.argv[1]))\n"
        if video:
            body += (f"out = sys.argv[sys.argv.index('--out-dir') + 1]\n"
                     f"os.makedirs(os.path.join(out, 'download'), exist_ok=True)\n"
                     f"shutil.copy({str(video)!r}, os.path.join(out, 'download', 'video.mp4'))\n")
    script.write_text(body)
    return script


os.environ.setdefault("PROMO_TEST", "1")
