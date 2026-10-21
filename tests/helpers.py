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


def png(path: Path, w: int, h: int, rgb=(40, 44, 60), band: float = 1 / 8) -> Path:
    """A solid-colour PNG with a lighter top band (so it is not blank); `band` sets its height."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for y in range(h):
        c = (rgb[0] + 60, rgb[1] + 60, rgb[2] + 80) if y < h * band else rgb
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
        "style": {},  # the product's theme (THEME.json) is the style
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
        discover_offline(self.ws)
        return self

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def discover_offline(ws) -> dict:
    """The PRODUCT_THEME_DISCOVERY stage without launching anything (recorded as skipped)."""
    from promo_engine import discovery
    return discovery.run(ws, launch=False, inspect_mobile=False)


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


# ── synthetic reference videos with known structure ───────────────────────────────
# Each profile lists (scene source, seconds) and the transitions between scenes, and
# returns the ground truth the analyzer must recover. 25 fps, 320×180.
REF_FPS, REF_SIZE = 25, "320x180"
SCENE_SRC = {
    "red": "color=c=0xC0392B", "blue": "color=c=0x1F3A93", "yellow": "color=c=0xF4D03F",
    "navy": "color=c=0x0B1B3F", "orange": "color=c=0xE67E22", "green": "color=c=0x1E8449",
    "grey": "color=c=0xB0B0B0", "motion": "testsrc2",
}


def _scene(src: str, secs: float, out: Path) -> Path:
    if src == "pan":  # a pure camera pan (120 px/s, content moves left) across a still frame
        still = out.with_suffix(".png")
        ffmpeg("-f", "lavfi", "-i", "testsrc=s=640x360:d=1", "-frames:v", "1", str(still))
        vf = f"crop=320:180:x='min(t*120,320)':y=90"
        ffmpeg("-loop", "1", "-i", str(still), "-t", str(secs), "-r", str(REF_FPS), "-vf", vf, "-pix_fmt", "yuv420p", str(out))
    else:
        base = SCENE_SRC[src]
        sep = ":" if "=" in base else "="
        ffmpeg("-f", "lavfi", "-i", f"{base}{sep}s={REF_SIZE}:r={REF_FPS}:d={secs}", "-pix_fmt", "yuv420p", str(out))
    return out


REFERENCE_PROFILES = {
    # Fast and punchy: five short scenes on hard cuts, one internal-motion scene, one
    # camera pan, a fade to black at the end.
    "rapid": {"scenes": [("red", 1.2), ("motion", 1.6), ("blue", 1.0), ("pan", 1.6), ("yellow", 1.4)],
              "transitions": ["cut", "cut", "cut", "cut"], "fade_out": 0.6},
    # Slow and soft: fade in, long holds, a dissolve, a wipe and a dip to black.
    "slow": {"scenes": [("navy", 3.0), ("orange", 3.0), ("green", 3.0), ("grey", 3.0)],
             "transitions": [("fade", 0.6), ("wipeleft", 0.6), ("fadeblack", 0.8)], "fade_in": 0.5},
}


def make_reference(dest: Path, profile: str) -> dict:
    """Render the profile to `dest` and return its ground truth (boundary times, types)."""
    spec = REFERENCE_PROFILES[profile]
    work = dest.parent / f"_{profile}_parts"
    work.mkdir(parents=True, exist_ok=True)
    parts = [_scene(src, secs, work / f"s{i}.mp4") for i, (src, secs) in enumerate(spec["scenes"])]
    truth = {"boundaries": [], "types": []}
    if all(t == "cut" for t in spec["transitions"]):
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        joined = work / "joined.mp4"
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined))
        t = 0.0
        for (_, secs) in spec["scenes"][:-1]:
            t += secs
            truth["boundaries"].append((round(t, 3), round(t, 3)))
            truth["types"].append("cut")
        total = sum(s for _, s in spec["scenes"])
    else:
        inputs, chain, prev, t = [], [], "0:v", spec["scenes"][0][1]
        for p in parts:
            inputs += ["-i", str(p)]
        for k, (kind, d) in enumerate(spec["transitions"]):
            off = round(t - d, 3)
            label = f"x{k}"
            chain.append(f"[{prev}][{k + 1}:v]xfade=transition={kind}:duration={d}:offset={off}[{label}]")
            truth["boundaries"].append((off, round(off + d, 3)))
            truth["types"].append({"fade": "dissolve", "wipeleft": "wipe-left", "fadeblack": "dip-black"}[kind])
            prev = label
            t = off + spec["scenes"][k + 1][1]
        joined = work / "joined.mp4"
        ffmpeg(*inputs, "-filter_complex", ";".join(chain), "-map", f"[{prev}]", "-pix_fmt", "yuv420p", str(joined))
        total = t
    vf = []
    if spec.get("fade_in"):
        vf.append(f"fade=t=in:st=0:d={spec['fade_in']}")
    if spec.get("fade_out"):
        vf.append(f"fade=t=out:st={total - spec['fade_out']}:d={spec['fade_out']}")
    ffmpeg("-i", str(joined), "-f", "lavfi", "-i", f"sine=f=330:d={total}",
           *(["-vf", ",".join(vf)] if vf else []), "-map", "0:v", "-map", "1:a", "-pix_fmt", "yuv420p",
           "-c:v", "libx264", "-preset", "ultrafast", "-r", str(REF_FPS), "-c:a", "aac", "-shortest", str(dest))
    shutil.rmtree(work, ignore_errors=True)
    truth["duration"] = round(total, 3)
    truth["scenes"] = len(spec["scenes"])
    return truth


# ── a real, runnable web product (for live inspection and capture) ────────────────
WEB_CSS = """@font-face { font-family: 'Inter'; src: url('/fonts/Inter.ttf') format('truetype'); font-weight: 100 900; }
:root {
  --brand: #1F8A70; --ink: #111418; --paper: #F7F5F0;
  --background: #F7F5F0; --foreground: #111418; --primary: #1F8A70; --primary-foreground: #FFFFFF;
  --accent: #F2A541; --card: #FFFFFF; --border: #E3DFD6; --destructive: #D64545; --success: #2E9E5B;
  --radius: 14px;
}
.dark { --background: #0F1412; --foreground: #EEF3F1; --primary: #3FBF9B; --card: #18201D; --border: #26302C; }
body { margin: 0; font-family: 'Inter', sans-serif; background: var(--background); color: var(--foreground); }
header { display: flex; justify-content: space-between; align-items: center; padding: 20px 48px; border-bottom: 1px solid var(--border); }
.logo { font-weight: 700; letter-spacing: -0.02em; font-size: 22px; color: var(--primary); }
main { padding: 48px; }
h1 { font-size: 56px; letter-spacing: -0.03em; font-weight: 700; margin: 0 0 16px; }
.btn { display: inline-block; background: var(--primary); color: var(--primary-foreground); padding: 14px 22px; border-radius: var(--radius); font-weight: 600; text-decoration: none; border: 0; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(0,0,0,.06); padding: 24px; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 28px; }
.bar { height: 14px; border-radius: 7px; background: var(--primary); margin: 10px 0; }
.label { text-transform: uppercase; letter-spacing: .08em; font-size: 12px; color: #6B6E76; }
"""

WEB_SERVER = r"""
const http = require('http'); const fs = require('fs'); const path = require('path');
const port = Number((process.argv.find(a => /^\d+$/.test(a))) || process.env.PORT || 3100);
const shell = (title, body) => `<!doctype html><html><head><meta charset="utf-8"><title>${title} · Tallyboard</title>
<link rel="stylesheet" href="/styles/globals.css"></head><body><header><span class="logo">Tallyboard</span>
<nav><a class="btn" href="/reports">Open report</a></nav></header><main>${body}</main></body></html>`;
const pages = {
  '/': shell('Home', `<div class="label">Receipts in. A finished report out.</div><h1>Where did this month go?</h1>
    <p>Drop a folder of receipts. Tallyboard groups every total by category.</p><button class="btn">Start a report</button>
    <div class="grid"><div class="card"><div class="label">Step 1</div><h3>Drop receipts</h3></div>
    <div class="card"><div class="label">Step 2</div><h3>Grouped by category</h3></div>
    <div class="card"><div class="label">Step 3</div><h3>Export CSV</h3></div></div>`),
  '/reports': shell('October report', `<div class="label">October · demo data</div><h1>$2,418.60 this month</h1>
    <div class="grid">${[['Travel', 92], ['Food', 64], ['Software', 41], ['Office', 23], ['Hosting', 18], ['Other', 9]]
      .map(([c, w]) => `<div class="card"><div class="label">${c}</div><div class="bar" style="width:${w}%"></div></div>`).join('')}</div>
    <p><button class="btn">Export CSV</button></p>`),
  '/settings': shell('Settings', `<h1>Settings</h1><div class="card">Signed in as test.user@example.com</div>`),
  '/login': shell('Sign in', `<h1>Sign in</h1><div class="card">Email <input> Password <input type="password"></div>`),
};
http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === '/admin') { res.writeHead(302, { Location: '/login' }); return res.end(); }
  if (url.startsWith('/styles/') || url.startsWith('/fonts/')) {
    const f = path.join(__dirname, url.startsWith('/fonts/') ? 'public' : '', url);
    if (fs.existsSync(f)) { res.writeHead(200, { 'Content-Type': url.endsWith('.css') ? 'text/css' : 'font/ttf' }); return res.end(fs.readFileSync(f)); }
  }
  if (pages[url]) { res.writeHead(200, { 'Content-Type': 'text/html' }); return res.end(pages[url]); }
  res.writeHead(404, { 'Content-Type': 'text/html' }); res.end('<h1>404</h1>');
}).listen(port, () => console.log(`ready on http://localhost:${port}`));
"""


def free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_web_product(root: Path, port: int, *, broken: bool = False) -> Path:
    """make_product + a Node server that really serves the app (or, with `broken`, fails to start
    after printing a credential-shaped line, to test that reports never repeat it)."""
    make_product(root)
    pkg = json.loads((root / "package.json").read_text())
    pkg["scripts"]["dev"] = f"node server.js --port {port}"
    (root / "package.json").write_text(json.dumps(pkg, indent=2))
    for r in ("settings", "admin", "team", "login"):
        (root / "app" / r).mkdir(parents=True, exist_ok=True)
        (root / "app" / r / "page.tsx").write_text(f"export default function P() {{ return <main>{r}</main>; }}\n")
    (root / "styles" / "globals.css").write_text(WEB_CSS)
    (root / "public" / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SKILL / "renderer" / "public" / "fonts" / "Inter.ttf", root / "public" / "fonts" / "Inter.ttf")
    if broken:
        (root / "server.js").write_text("console.log('DATABASE_URL=postgres://demo:hunter2@db.internal/app');\n"
                                        "console.error('Error: Cannot find module \"next\"'); process.exit(1);\n")
    else:
        (root / "server.js").write_text(WEB_SERVER)
    return root


FLUTTER_MAIN = r"""
import 'package:flutter/material.dart';

const brand = Color(0xFF1F8A70);
const paper = Color(0xFFF7F5F0);
const ink = Color(0xFF111418);

final lightTheme = ThemeData(
  brightness: Brightness.light,
  colorScheme: ColorScheme.fromSeed(seedColor: brand, primary: brand, surface: Color(0xFFFFFFFF)),
  scaffoldBackgroundColor: paper,
  useMaterial3: true,
);
final darkTheme = ThemeData(
  brightness: Brightness.dark,
  colorScheme: ColorScheme.fromSeed(seedColor: Color(0xFF3FBF9B), brightness: Brightness.dark),
  scaffoldBackgroundColor: Color(0xFF0F1412),
  useMaterial3: true,
);

void main() => runApp(const Tallyboard());

class Tallyboard extends StatelessWidget {
  const Tallyboard({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Tallyboard',
        debugShowCheckedModeBanner: false,
        theme: lightTheme,
        darkTheme: darkTheme,
        themeMode: ThemeMode.light,
        routes: {
          '/': (c) => const Page(title: 'Where did this month go?', body: 'Drop receipts. Tallyboard groups every total.', cta: 'Start a report'),
          '/history': (c) => const Page(title: 'History', body: 'September · August · July (demo data)', cta: 'Open report'),
          '/result': (c) => const Page(title: '\$2,418.60 this month', body: 'Travel · Food · Software · Office', cta: 'Export CSV'),
        },
      );
}

class Page extends StatelessWidget {
  const Page({super.key, required this.title, required this.body, required this.cta});
  final String title, body, cta;
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Tallyboard', style: TextStyle(color: brand, fontWeight: FontWeight.w700))),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w700, color: ink)),
            const SizedBox(height: 12),
            Text(body, style: const TextStyle(fontSize: 18)),
            const SizedBox(height: 24),
            for (final w in [0.9, 0.6, 0.4])
              Container(margin: const EdgeInsets.symmetric(vertical: 6), height: 14,
                  width: 300 * w, decoration: BoxDecoration(color: brand, borderRadius: BorderRadius.circular(7))),
            const SizedBox(height: 24),
            FilledButton(onPressed: () {}, child: Text(cta)),
          ]),
        ),
      );
}
"""


def make_flutter_product(root: Path) -> Path:
    """A real Flutter iOS app (`flutter create`, offline) with a theme, three routes and a
    `tallyboard://` deep-link scheme, so a simulator run can reach every screen."""
    root.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["flutter", "create", "--org", "com.example", "--project-name", "tallyboard", "--platforms", "ios",
                    "--offline", root.name], cwd=root.parent, check=True, capture_output=True)
    (root / "lib" / "main.dart").write_text(FLUTTER_MAIN)
    (root / "README.md").write_text("# Tallyboard\n\nTallyboard turns receipts into a monthly expense report.\n")
    plist = root / "ios" / "Runner" / "Info.plist"
    text = plist.read_text()
    extra = ("\t<key>FlutterDeepLinkingEnabled</key>\n\t<true/>\n\t<key>CFBundleURLTypes</key>\n\t<array>\n\t\t<dict>\n"
             "\t\t\t<key>CFBundleURLSchemes</key>\n\t\t\t<array>\n\t\t\t\t<string>tallyboard</string>\n\t\t\t</array>\n"
             "\t\t</dict>\n\t</array>\n")
    plist.write_text(text.replace("<dict>\n", "<dict>\n" + extra, 1))
    return root
