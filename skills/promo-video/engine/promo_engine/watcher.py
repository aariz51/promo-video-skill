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
import shutil
import subprocess
import sys
from pathlib import Path

from . import reference_input
from .config import Workspace
from .reference_input import VIDEO_EXT
from .util import PromoError, fmt_time, parse_time, read_json, run, write_json
from .youtube import parse_youtube_url

WATCH_INSTALL_HINT = (
    "install the watch skill: in Claude Code run "
    "`/plugin marketplace add bradautomates/claude-video` then `/plugin install watch@claude-video`, "
    "or `npx skills add bradautomates/claude-video -g`. "
    "Set PROMO_WATCH_SKILL_DIR if it lives somewhere else."
)

# The watch skill itself broke (not the video): an ffmpeg option or extraction step failed.
TOOL_FAILURE = re.compile(r"Unrecognized option '[^']+'|frame extraction failed|scene extraction failed|"
                          r"keyframe extraction failed")
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


def _run_watch(script: Path, source: str, out_dir: Path, detail: str, no_whisper: bool = False) -> tuple[int, str, str]:
    cmd = [sys.executable, str(script), source, "--detail", detail, "--out-dir", str(out_dir)]
    if no_whisper:
        cmd.append("--no-whisper")  # never send audio to a paid transcription API
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


def _download(url: str, dest: Path) -> Path:
    """yt-dlp straight to a file: the fallback when the watch skill is not installed."""
    if shutil.which("yt-dlp") is None:
        raise PromoError("the watch skill is not installed and yt-dlp is missing, so the reference cannot be fetched",
                         hint=WATCH_INSTALL_HINT + " Or download the video yourself and pass its local path. "
                              "No analysis is invented.")
    dest.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(["yt-dlp", "--no-playlist", "-f", "bv*[height<=720]+ba/b[height<=720]/b",
                          "--merge-output-format", "mp4", "-o", str(dest / "video.%(ext)s"), "--", url],
                         capture_output=True, text=True)
    got = sorted(dest.glob("video.*"))
    if res.returncode != 0 or not got:
        tail = "\n  ".join((res.stderr or res.stdout).strip().splitlines()[-4:])
        raise PromoError(f"could not download the reference ({url}).\n  {tail}",
                         hint="check the URL is public and points at one video, or supply a local file. "
                              "No analysis is invented.")
    return got[0]


def _video_in(paths) -> Path | None:
    return next((p for p in paths if p.is_file() and p.suffix.lower() in VIDEO_EXT), None)


def watch(ws: Workspace, source: str, *, detail: str = "balanced", script: Path | None = None,
          refresh: bool = False, no_whisper: bool = False) -> dict:
    """Watch the reference and measure it: inspiration/evidence.json, pacing.json and
    reference/breakdown.json (+ frames and contact sheets).

    The watch skill supplies frames and the transcript. If it is not installed, a local file
    is measured directly and a URL is fetched with yt-dlp (no transcript then, and the
    evidence says so). A previous download of the same source is reused unless `refresh`.
    """
    ref = reference_input.resolve(source, base=Path.cwd())
    if ref.kind == "none":
        raise PromoError("there is no reference video to watch (the run is in autonomous mode)")
    src = ref.source
    video_id = parse_youtube_url(src).id if ref.kind == "youtube" else None
    work = ws.inspiration_dir / "watch"

    old = read_json(ws.evidence) if ws.evidence.exists() and not refresh else None
    if old and old.get("canonical") == src and old.get("videoFile") and (ws.root / old["videoFile"]).is_file():
        video_file, ev, used_watch, note = ws.root / old["videoFile"], old, old.get("watch", {}).get("used"), "reused"
    else:
        if script is None:
            try:
                script = find_watch_skill() / "scripts" / "watch.py"
            except PromoError:
                script = None
        work.mkdir(parents=True, exist_ok=True)
        if script is not None:
            code, out, err = _run_watch(script, src, work, detail, no_whisper)
            used = src
            if (code != 0 or "## Frames" not in out) and video_id:
                fb = _fallback_download(src, work / "fallback")
                if fb:
                    code, out, err = _run_watch(script, str(fb), work, detail, no_whisper)
                    used = str(fb)
            tool_failure = code != 0 and bool(TOOL_FAILURE.search(err or ""))
            if (code != 0 or "## Frames" not in out) and not tool_failure:
                tail = "\n  ".join((err or out).strip().splitlines()[-6:])
                raise PromoError(
                    f"could not analyse the reference video ({src}).\n  {tail}",
                    hint="check the URL is public, not age/region-locked, and points at one video (or supply a local "
                         "file), or continue without a reference (autonomous mode). No analysis is invented.",
                )
            if tool_failure:
                # The skill ran but its frame extraction broke on this machine's ffmpeg (claude-video
                # 0.2.0 passes -vsync, which ffmpeg 7+ removed). Keep what still works, its
                # transcript, and measure the frames with promo's own analyzer instead.
                reason = TOOL_FAILURE.search(err).group(0)
                code_t, out_t, _ = _run_watch(script, src, work, "transcript", no_whisper)
                ev = parse_report(out_t) if code_t == 0 else {"title": None, "duration": 0.0, "resolution": None,
                                                              "frames": [], "transcript": {"available": False,
                                                              "source": "not available (watch failed)", "lines": []}}
                if code_t == 0:
                    (ws.inspiration_dir / "watch-report.md").write_text(out_t)
                ev["frames"] = []
                video_file = _video_in([Path(src)] + sorted((work / "download").glob("video.*"))) \
                    or _download(src, work / "download")
                used_watch = code_t == 0
                note = (f"watch skill frame extraction failed on this ffmpeg ({reason}); "
                        f"transcript {'from watch' if code_t == 0 else 'unavailable'}, frames measured by promo")
            else:
                (ws.inspiration_dir / "watch-report.md").write_text(out)
                ev = parse_report(out)
                if not ev["frames"]:
                    raise PromoError("the watch skill returned no frames, so the video cannot be analysed visually",
                                     hint="re-run with a different URL or check `yt-dlp` can download it")
                video_file = _video_in([Path(used)] + sorted((work / "download").glob("video.*")))
                used_watch, note = True, "watch skill"
        else:
            video_file = Path(src) if ref.kind == "file" else _download(src, work / "download")
            ev = {"title": None, "duration": 0.0, "resolution": None, "frames": [],
                  "transcript": {"available": False, "source": "not available: the watch skill is not installed",
                                 "lines": []}}
            used_watch, note = False, "watch skill not installed; measured by promo's own analyzer"
        if video_file is None:
            raise PromoError("the reference was watched but no video file was kept, so it cannot be measured",
                             hint="re-run `promo watch --refresh`, or pass a local file")

    # Measure the file itself: the report's duration can describe a different stream.
    from . import reference  # local import: reference imports nothing from here
    bd = reference.analyze(video_file, ws.reference_dir, transcript=ev.get("transcript"), source=src)
    duration = bd["metadata"]["duration"]
    pacing = pacing_from_cuts(detect_cuts(video_file), duration)
    write_json(ws.inspiration_dir / "pacing.json", pacing)

    for fr in ev.get("frames", []):
        p = Path(fr["path"])
        if p.is_absolute() and p.is_relative_to(ws.root):
            fr["path"] = p.relative_to(ws.root).as_posix()
    rel = (lambda p: p.relative_to(ws.root).as_posix() if p.is_relative_to(ws.root) else str(p))
    evidence = {
        "source": source,
        "canonical": src,
        "kind": ref.kind,
        "videoId": video_id,
        "videoFile": rel(Path(video_file).resolve()),
        "watch": {"used": bool(used_watch), "note": note},
        "title": ev.get("title"),
        "duration": duration,
        "resolution": f"{bd['metadata']['width']}x{bd['metadata']['height']}",
        "frames": ev.get("frames", []),
        "transcript": ev.get("transcript"),
        "pacing": pacing,
        "breakdown": "reference/breakdown.json",
        "report": "inspiration/watch-report.md" if (ws.inspiration_dir / "watch-report.md").exists() else None,
    }
    write_json(ws.evidence, evidence)
    evidence["reference"] = bd
    return evidence


def evidence_summary(ev: dict) -> str:
    from . import reference
    t = ev["transcript"] or {"available": False, "lines": []}
    head = (f"{ev.get('title') or ev['source']} · watch: {ev['watch']['note']} · {len(ev['frames'])} watch frames · "
            f"transcript: {'yes, ' + str(len(t['lines'])) + ' lines' if t['available'] else 'none'}")
    return head + ("\nMeasured: " + reference.summary(ev["reference"]) if ev.get("reference") else "")
