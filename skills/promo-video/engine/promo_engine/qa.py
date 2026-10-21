"""Layer 8: QA. Checks the rendered film against the plan it was rendered from.

A successful render is not verification. QA inspects the encoded file (resolution, frame
rate, duration, streams, decode errors, black and frozen stretches), the audio (present,
narration placed inside its scenes, no music), and exports one still per scene so the
agent can look at every scene for overflow and layout problems.
"""
from __future__ import annotations

import array
import json
import math
import re
from pathlib import Path

from . import sound
from .config import ASPECTS, Workspace
from .util import Report, ffprobe_json, fmt_time, read_json, run, write_json

SILENCE_DBFS = -45.0


def _pcm_mono(path: Path, rate: int = 8000) -> array.array:
    raw = run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
              text=False).stdout
    a = array.array("h")
    a.frombytes(raw)
    return a


def _dbfs(chunk) -> float:
    if not chunk:
        return -120.0
    rms = math.sqrt(sum(v * v for v in chunk) / len(chunk)) / 32768
    return 20 * math.log10(rms + 1e-9)


def check_no_music(audio_manifest: dict, master: Path, rc: dict) -> Report:
    """Music can only enter through the mix, so prove the mix: allowed sources only, short
    effects only, and near-silence wherever no cue or voice line is sounding."""
    r = Report()
    where = "audio"
    if audio_manifest.get("music") is not False:
        r.error(where, "audio manifest does not assert music=false")
    allowed_sfx = {f"sfx/{f}" for f in sound.LIBRARY.values()}
    busy: list[tuple[float, float]] = []
    for s in audio_manifest.get("sources", []):
        kind = s.get("kind")
        if kind == "sfx":
            if s["source"] not in allowed_sfx:
                r.error(where, f"unknown effect source in mix: {s['source']}")
            if s["seconds"] > sound.MAX_EFFECT_SECONDS:
                r.error(where, f"effect {s['source']} is {s['seconds']}s long; long files can carry music")
            busy.append((s["at"], s["at"] + s["seconds"] + 0.25))
        elif kind == "voice":
            busy.append((s["at"], s["at"] + s["seconds"] + 0.25))
        elif kind == "ambience":
            if "non-melodic" not in s.get("source", ""):
                r.error(where, "ambience layer is not the procedural non-melodic bed")
        else:
            r.error(where, f"unexpected source kind in mix: {kind}")
    if rc["sound"].get("ambience") or not master.is_file():
        return r
    pcm = _pcm_mono(master)
    rate, win = 8000, 4000  # 0.5 s windows
    busy.sort()
    loud = []
    for i in range(0, len(pcm) - win, win):
        a, b = i / rate, (i + win) / rate
        if any(x < b and y > a for x, y in busy):
            continue
        db = _dbfs(pcm[i:i + win])
        if db > SILENCE_DBFS:
            loud.append(f"{fmt_time(a)} ({db:.0f} dBFS)")
    if loud:
        r.error(where, "sound between cues where there should be silence (possible bed/music): " + ", ".join(loud[:5]))
    return r


def check_video(path: Path, aspect: str, rc: dict, scale: float = 1.0) -> tuple[Report, dict]:
    r = Report()
    where = path.name
    info = ffprobe_json(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    facts: dict = {"file": str(path), "bytes": path.stat().st_size}
    if not v:
        r.error(where, "no video stream")
        return r, facts
    comp = ASPECTS[aspect]
    want_w, want_h = round(comp["width"] * scale), round(comp["height"] * scale)
    facts.update(width=v["width"], height=v["height"], codec=v["codec_name"])
    if (v["width"], v["height"]) != (want_w, want_h):
        r.error(where, f"resolution {v['width']}×{v['height']}, expected {want_w}×{want_h}")
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    fps = num / den
    facts["fps"] = round(fps, 3)
    if abs(fps - rc["fps"]) > 0.01:
        r.error(where, f"frame rate {fps:.2f}, expected {rc['fps']}")
    dur = float(info["format"]["duration"])
    facts["duration"] = round(dur, 3)
    if abs(dur - rc["duration"]) > 2 / rc["fps"] + 0.05:
        r.error(where, f"duration {dur:.2f}s, timeline says {rc['duration']:.2f}s")
    if not a:
        r.error(where, "no audio stream")
    else:
        facts["audio"] = {"codec": a["codec_name"], "channels": a.get("channels")}
    dec = run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"], check=False)
    if dec.returncode != 0 or dec.stderr.strip():
        r.error(where, "decode errors: " + dec.stderr.strip().splitlines()[0][:160])
    det = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "blackdetect=d=1.0:pix_th=0.06",
               "-af", "volumedetect", "-f", "null", "-"], check=False).stderr
    blacks = [(float(s), float(e)) for s, e in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", det)]
    long_black = [(s, e) for s, e in blacks if s < dur - 1.6]
    if long_black:
        r.error(where, "black frames for over 1s at " + ", ".join(f"{fmt_time(s)}–{fmt_time(e)}" for s, e in long_black))
    mv = re.search(r"mean_volume: (-?[\d.]+) dB", det)
    if a and mv:
        facts["meanVolume"] = float(mv.group(1))
        if float(mv.group(1)) < -60:
            r.error(where, f"audio is effectively silent (mean {mv.group(1)} dB)")
    fz = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vf", "freezedetect=n=0.001:d=5", "-an", "-f", "null", "-"],
             check=False).stderr
    frozen = re.findall(r"freeze_start: ([\d.]+)", fz)
    if frozen:
        r.warn(where, f"picture is frozen for 5s+ from {', '.join(fmt_time(float(x)) for x in frozen[:3])}")
    return r, facts


def check_narration(vo_manifest: dict, rc: dict) -> Report:
    r = Report()
    fps = rc["fps"]
    bounds = {s["id"]: (s["from"] / fps, (s["from"] + s["durationInFrames"]) / fps) for s in rc["scenes"]}
    want = rc["narration"]["lines"]
    got = vo_manifest.get("lines", [])
    if rc["narration"]["enabled"]:
        if len(got) != len(want):
            r.error("narration", f"{len(got)} voice lines rendered, timeline has {len(want)}")
        for ln in got:
            a, b = bounds.get(ln.get("scene"), (0, rc["duration"]))
            end = ln["at"] + ln["seconds"]
            if ln["at"] < a - 0.01 or end > b + 0.5:
                r.error("narration", f"line in '{ln.get('scene')}' runs {fmt_time(ln['at'])}–{fmt_time(end)}, "
                        f"outside its scene {fmt_time(a)}–{fmt_time(b)}")
        for x, y in zip(got, got[1:]):
            if x["at"] + x["seconds"] > y["at"] + 0.02:
                r.error("narration", f"lines overlap at {fmt_time(y['at'])}")
    elif not rc["narration"].get("reason"):
        r.error("narration", "no narration and no reason recorded")
    return r


def export_stills(path: Path, rc: dict, dest: Path) -> list[str]:
    """Two stills per scene from the encoded file: building (45%) and settled (85%)."""
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("*.jpg"):
        old.unlink()
    out = []
    for i, s in enumerate(rc["scenes"], 1):
        for tag, pos in (("a", 0.45), ("b", 0.85)):
            t = (s["from"] + s["durationInFrames"] * pos) / rc["fps"]
            f = dest / f"{i:02d}-{s['id']}-{tag}.jpg"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                 "-vf", "scale='min(960,iw)':-2", "-q:v", "3", str(f)])
            out.append(str(f))
    return out


def run_qa(ws: Workspace, videos: dict[str, Path], scale: float = 1.0) -> Report:
    """`scale` is the render scale actually used (draft renders are half size)."""
    rc = read_json(ws.render_config)
    rep = Report()
    facts: dict = {"videos": {}}
    if not videos:
        rep.error("render", "no rendered video found")
    for aspect, path in videos.items():
        if not path.is_file() or path.stat().st_size == 0:
            rep.error("render", f"{aspect}: {path} was not produced")
            continue
        r, f = check_video(path, aspect, rc, scale)
        rep.extend(r)
        f["stills"] = [_rel(x, ws.root) for x in export_stills(path, rc, ws.qa_dir / "frames" / aspect.replace(":", "x"))]
        f["file"] = _rel(f["file"], ws.root)
        facts["videos"][aspect] = f
    for s in rc["scenes"]:
        if s["durationInFrames"] < 1.5 * rc["fps"]:
            rep.error("timeline", f"scene {s['id']} is shorter than 1.5s")
    if sum(s["durationInFrames"] for s in rc["scenes"]) != rc["durationInFrames"]:
        rep.error("timeline", "scene durations do not add up to the film's length")
    vo_path = ws.vo_dir / "manifest.json"
    vo = json.loads(vo_path.read_text()) if vo_path.exists() else {"lines": []}
    rep.extend(check_narration(vo, rc))
    am_path = ws.root / "build" / "audio-manifest.json"
    if am_path.exists():
        rep.extend(check_no_music(json.loads(am_path.read_text()), ws.master_audio, rc))
    else:
        rep.error("audio", "no audio manifest; the mix was not built by `promo audio`")
    facts["narrationLines"] = len(vo.get("lines", []))
    facts["voiceEngine"] = vo.get("engine")
    write_json(ws.qa_dir / "qa.json", {"ok": rep.ok, "issues": [i.__dict__ for i in rep.issues], **facts})
    ws.qa_report.write_text(report_md(rep, facts, rc))
    return rep


def _rel(p, root: Path | None) -> str:
    """Workspace-relative paths in the report: it is meant to be shared."""
    try:
        return Path(p).resolve().relative_to(root).as_posix() if root else str(p)
    except ValueError:
        return str(p)


def report_md(rep: Report, facts: dict, rc: dict) -> str:
    lines = [f"# QA report — {rc['product']}", "", f"Result: **{'PASS' if rep.ok else 'FAIL'}** "
             f"({len(rep.errors)} errors, {len(rep.warnings)} warnings)", "", "## Checks", "",
             "- Render produced each requested file, with a video and an audio stream",
             "- Resolution, frame rate and duration match render-config.json",
             "- Full decode pass without errors; no black stretch over 1 s; frozen stretches reported",
             "- Scene timing adds up; no scene under 1.5 s",
             "- Narration: every line rendered, inside its scene, no overlaps",
             "- Audio present; mix contains only library effects, voice and (optional) non-melodic ambience",
             "- Near-silence wherever no cue or line is sounding, so no background music or bed",
             "- Two stills per scene exported for visual review (text overflow, layout)", "", "## Files", ""]
    for aspect, f in facts["videos"].items():
        lines.append(f"- {aspect}: `{f['file']}` · {f.get('width')}×{f.get('height')} · {f.get('fps')} fps · "
                     f"{f.get('duration')} s · audio {f.get('audio', {}).get('codec', 'none')} · "
                     f"mean {f.get('meanVolume', '?')} dB · {f['bytes'] / 1e6:.1f} MB")
    lines += ["", f"Narration: {facts['narrationLines']} lines via {facts['voiceEngine'] or 'none'}", "",
              "## Issues", ""]
    lines += [f"- {i}" for i in rep.issues] or ["- none"]
    lines += ["", "## Stills for review", ""]
    for aspect, f in facts["videos"].items():
        lines += [f"- {aspect}: `{Path(f['stills'][0]).parent}` ({len(f['stills'])} frames)"] if f.get("stills") else []
    return "\n".join(lines) + "\n"
