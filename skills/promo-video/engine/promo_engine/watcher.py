"""Layer 3: VIDEO WATCHER.

A thin adapter over the `watch` skill from bradautomates/claude-video. It does not
re-implement video analysis. It runs `watch.py`, keeps the report, parses the frames and
transcript it returns into `inspiration/evidence.json`, and adds one measurement `watch`
does not provide: hard-cut detection for pacing (`inspiration/pacing.json`).

The agent then Reads the frames listed in evidence.json and writes the
YOUTUBE INSPIRATIONAL PROMPT from them. If watching fails, this raises: the pipeline never
continues on an analysis it did not perform.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
from pathlib import Path

from . import reference_input
from .config import Workspace
from .util import PromoError, fmt_time, parse_time, run, write_json
from .youtube import parse_youtube_url

WATCH_INSTALL_HINT = (
    "install the watch skill: in Claude Code run "
    "`/plugin marketplace add bradautomates/claude-video` then `/plugin install watch@claude-video`, "
    "or `npx skills add bradautomates/claude-video -g`. "
    "Set PROMO_WATCH_SKILL_DIR if it lives somewhere else."
)

_FRAME = re.compile(r"^- `(?P<path>[^`]+)` \(t=(?P<t>[\d:]+), reason=(?P<reason>[^)]*)\)")
_LINE = re.compile(r"^\[(?P<t>\d+:\d{2}(?::\d{2})?)\]\s*(?P<text>.*)$")
_FIELD = re.compile(r"^- \*\*(?P<k>[^:*]+):\*\* (?P<v>.*)$")


def find_watch_skill() -> Path:
    """Locate watch.py in any standard install layout."""
    env = os.environ.get("PROMO_WATCH_SKILL_DIR")
    candidates = [Path(env)] if env else []
    home = Path.home()
    candidates += [home / ".claude/skills/watch", home / ".agents/skills/watch", home / ".codex/skills/watch"]
    candidates += [Path(p) for p in sorted(glob.glob(str(home / ".claude/plugins/cache/*/watch/*/skills/watch")))]
    for c in candidates:
        if (c / "scripts" / "watch.py").is_file():
            return c
    raise PromoError("the `watch` skill (claude-video) is not installed", hint=WATCH_INSTALL_HINT)


def parse_report(text: str) -> dict:
    """Parse the markdown report `watch.py` prints into structured evidence."""
    fields: dict[str, str] = {}
    frames: list[dict] = []
    transcript: list[dict] = []
    section = None
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section is None:
            m = _FIELD.match(line)
            if m:
                fields[m["k"].strip().lower()] = m["v"].strip()
        elif section == "frames":
            m = _FRAME.match(line)
            if m:
                frames.append({"t": parse_time(m["t"]), "path": m["path"], "reason": m["reason"].strip()})
        elif section == "transcript":
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                m = _LINE.match(line)
                if m:
                    transcript.append({"t": parse_time(m["t"]), "text": m["text"].strip()})
    duration = 0.0
    dm = re.search(r"\(([\d.]+)s\)", fields.get("duration", ""))
    if dm:
        duration = float(dm.group(1))
    tsrc = fields.get("transcript", "")
    return {
        "title": fields.get("title"),
        "duration": duration,
        "resolution": fields.get("resolution"),
        "frames": frames,
        "transcript": {
            "available": bool(transcript),
            "source": tsrc or "none available",
            "lines": transcript,
        },
    }


def detect_cuts(video: str | Path, threshold: float = 0.3) -> list[float]:
    """Hard-cut timestamps via ffmpeg's scene score. Deterministic for a given file."""
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-an", "-vf",
               f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"], check=False)
    return [round(float(m), 3) for m in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def pacing_from_cuts(cuts: list[float], duration: float) -> dict:
    """Shot lengths and how cutting density moves through the film, by quarter."""
    bounds = [0.0] + [c for c in cuts if 0.05 < c < duration - 0.05] + [duration]
    shots = [round(b - a, 3) for a, b in zip(bounds, bounds[1:]) if b - a > 0.04]
    quarters = []
    for q in range(4):
        a, b = duration * q / 4, duration * (q + 1) / 4
        n = sum(1 for c in cuts if a <= c < b)
        quarters.append({"from": round(a, 2), "to": round(b, 2), "cuts": n,
                         "cutsPerMinute": round(n / max(b - a, 1e-6) * 60, 1)})
    avg = sum(shots) / len(shots) if shots else duration
    return {
        "duration": round(duration, 3),
        "cuts": [round(c, 3) for c in cuts],
        "cutCount": len(cuts),
        "shotCount": len(shots),
        "averageShot": round(avg, 2),
        "shortestShot": min(shots) if shots else duration,
        "longestShot": max(shots) if shots else duration,
        "quarters": quarters,
    }


def _run_watch(script: Path, source: str, out_dir: Path, detail: str) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), source, "--detail", detail, "--out-dir", str(out_dir)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr


def _fallback_download(url: str, dest: Path) -> Path | None:
    """YouTube sometimes 403s the default client; a progressive mweb stream usually works."""
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / "fallback.mp4"
    res = subprocess.run(["yt-dlp", "--no-playlist", "--extractor-args", "youtube:player_client=mweb",
                          "-f", "18/b[height<=720]", "-o", str(out), "--", url],
                         capture_output=True, text=True)
    return out if res.returncode == 0 and out.exists() and out.stat().st_size > 0 else None


def watch(ws: Workspace, source: str, *, detail: str = "balanced", script: Path | None = None) -> dict:
    """Watch the inspiration video and write inspiration/evidence.json + pacing.json."""
    ref = reference_input.resolve(source, base=Path.cwd())
    if ref.kind == "none":
        raise PromoError("there is no reference video to watch (the run is in autonomous mode)")
    src = ref.source
    video_id = parse_youtube_url(src).id if ref.kind == "youtube" else None
    script = script or find_watch_skill() / "scripts" / "watch.py"
    work = ws.inspiration_dir / "watch"
    work.mkdir(parents=True, exist_ok=True)

    code, out, err = _run_watch(script, src, work, detail)
    used = src
    if (code != 0 or "## Frames" not in out) and video_id:
        fb = _fallback_download(src, work / "fallback")
        if fb:
            code, out, err = _run_watch(script, str(fb), work, detail)
            used = str(fb)
    if code != 0 or "## Frames" not in out:
        tail = "\n  ".join((err or out).strip().splitlines()[-6:])
        raise PromoError(
            f"could not analyse the inspiration video ({src}).\n  {tail}",
            hint="check the URL is public, not age/region-locked, and points at one video (or supply a local "
                 "file), or continue without a reference (autonomous mode). No analysis is invented.",
        )
    (ws.inspiration_dir / "watch-report.md").write_text(out)
    ev = parse_report(out)
    if not ev["frames"]:
        raise PromoError("the watch skill returned no frames, so the video cannot be analysed visually",
                         hint="re-run with a different URL or check `yt-dlp` can download it")

    video_file = next((p for p in [Path(used)] + sorted((work / "download").glob("video.*"))
                       if p.is_file() and p.suffix.lower() in (".mp4", ".mkv", ".webm", ".mov")), None)
    pacing = None
    if video_file:
        # Measure the file itself: the report's duration can describe a different stream.
        duration = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "default=nw=1:nk=1", str(video_file)]).stdout.strip())
        pacing = pacing_from_cuts(detect_cuts(video_file), duration)
        write_json(ws.inspiration_dir / "pacing.json", pacing)

    for fr in ev["frames"]:
        p = Path(fr["path"])
        if p.is_absolute() and p.is_relative_to(ws.root):
            fr["path"] = p.relative_to(ws.root).as_posix()
    evidence = {
        "source": source,
        "canonical": src,
        "videoId": video_id,
        "title": ev["title"],
        "duration": ev["duration"],
        "resolution": ev["resolution"],
        "frames": ev["frames"],
        "transcript": ev["transcript"],
        "pacing": pacing,
        "report": "inspiration/watch-report.md",
    }
    write_json(ws.evidence, evidence)
    return evidence


def evidence_summary(ev: dict) -> str:
    p = ev.get("pacing") or {}
    t = ev["transcript"]
    return (f"{ev.get('title') or ev['source']} · {fmt_time(ev['duration'])} · {len(ev['frames'])} frames · "
            f"{p.get('cutCount', '?')} cuts (avg shot {p.get('averageShot', '?')} s) · "
            f"transcript: {'yes, ' + str(len(t['lines'])) + ' lines' if t['available'] else 'none'}")
