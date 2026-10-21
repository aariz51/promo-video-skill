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
from .config import ASPECTS, Workspace, render_scale
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


def _busy_windows(sources: list[dict]) -> list[tuple[float, float]]:
    return sorted((x["at"], x["at"] + x["seconds"] + 0.25) for x in sources if x.get("kind") in ("sfx", "voice"))


def loud_outside(pcm, busy: list[tuple[float, float]], rate: int = 8000, win: int = 4000) -> list[str]:
    """0.5 s windows that carry sound although no cue or voice line is sounding."""
    loud = []
    for i in range(0, len(pcm) - win, win):
        a, b = i / rate, (i + win) / rate
        if any(x < b and y > a for x, y in busy):
            continue
        db = _dbfs(pcm[i:i + win])
        if db > SILENCE_DBFS:
            loud.append(f"{fmt_time(a)} ({db:.0f} dBFS)")
    return loud


def check_no_music(audio_manifest: dict, master: Path, rc: dict) -> Report:
    """Music can only enter through the mix, so prove the mix: allowed sources only, short
    effects only, sources that match the audio policy, and near-silence wherever no cue or
    voice line is sounding. `master` may also be an encoded film (its audio is decoded)."""
    r = Report()
    where = "audio"
    if audio_manifest.get("music") is not False:
        r.error(where, "audio manifest does not assert music=false")
    pol = rc.get("audioPolicy") or {"mode": "voiceover", "voiceover": True, "soundEffects": True}
    mpol = audio_manifest.get("policy")
    if mpol and mpol.get("mode") != pol["mode"]:
        r.error(where, f"the mix was built for '{mpol.get('mode')}' but the film is '{pol['mode']}'; re-run `promo audio`")
    allowed_sfx = {sound.source_name(n) for n in sound.LIBRARY}
    for s in audio_manifest.get("sources", []):
        kind = s.get("kind")
        if kind == "sfx":
            if not pol["soundEffects"]:
                r.error(where, f"effect {s['source']} is in the mix but the audio mode is '{pol['mode']}'")
            if s["source"] not in allowed_sfx:
                r.error(where, f"unknown effect source in mix: {s['source']}")
            if s["seconds"] > sound.MAX_EFFECT_SECONDS:
                r.error(where, f"effect {s['source']} is {s['seconds']}s long; long files can carry music")
        elif kind == "voice":
            if not pol["voiceover"]:
                r.error(where, f"speech ({s['source']}) is in the mix but the audio mode is '{pol['mode']}'")
        elif kind == "ambience":
            if "non-melodic" not in s.get("source", ""):
                r.error(where, "ambience layer is not the procedural non-melodic bed")
        else:
            r.error(where, f"unexpected source kind in mix: {kind}")
    if pol["mode"] == "silent":
        if audio_manifest.get("sources"):
            r.error(where, "the audio mode is 'silent' but the mix lists sources")
        return r
    if rc["sound"].get("ambience") or not master.is_file():
        return r
    loud = loud_outside(_pcm_mono(master), _busy_windows(audio_manifest.get("sources", [])))
    if loud:
        r.error(where, f"sound between cues where there should be silence (possible bed/music"
                f"{'' if pol['voiceover'] else ' or speech'}) in {master.name}: " + ", ".join(loud[:5]))
    return r


def max_volume(path: Path) -> float | None:
    det = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
              check=False).stderr
    m = re.search(r"max_volume: (-?[\d.]+|-inf) dB", det)
    if not m:
        return None
    return -200.0 if m.group(1) == "-inf" else float(m.group(1))


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
    silent = (rc.get("audioPolicy") or {}).get("mode") == "silent"
    if silent:
        if a:
            # Accepted only when independently verified as digital silence.
            peak = max_volume(path)
            facts["audio"] = {"codec": a["codec_name"], "channels": a.get("channels"), "peak": peak}
            if peak is None or peak > -90:
                r.error(where, f"silent mode, but the file has an audible audio stream (peak {peak} dB)")
            else:
                r.warn(where, "silent mode: the file carries an audio stream, verified silent")
        else:
            facts["audio"] = None
    elif not a:
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
    mv = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", det)
    if a and mv and not silent:
        mean = -200.0 if mv.group(1) == "-inf" else float(mv.group(1))
        facts["meanVolume"] = mean
        if mean < -60:
            r.error(where, f"audio is effectively silent (mean {mv.group(1)} dB) although the mode has sound")
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
    pol = rc.get("audioPolicy") or {"voiceover": True, "mode": "voiceover"}
    if not pol["voiceover"] and got:
        r.error("narration", f"{len(got)} voice line(s) exist but the audio mode is '{pol['mode']}'")
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


def run_qa(ws: Workspace, videos: dict[str, Path], quality: str = "final") -> Report:
    """`quality` is the one the files were rendered at (draft renders are smaller)."""
    rc = read_json(ws.render_config)
    rep = Report()
    facts: dict = {"videos": {}}
    if not videos:
        rep.error("render", "no rendered video found")
    for aspect, path in videos.items():
        if not path.is_file() or path.stat().st_size == 0:
            rep.error("render", f"{aspect}: {path} was not produced")
            continue
        r, f = check_video(path, aspect, rc, render_scale(aspect, quality))
        rep.extend(r)
        f["stills"] = [_rel(x, ws.root) for x in export_stills(path, rc, ws.qa_dir / "frames" / aspect.replace(":", "x"))]
        f["file"] = _rel(f["file"], ws.root)
        facts["videos"][aspect] = f
    for s in rc["scenes"]:
        if s["durationInFrames"] < 0.5 * rc["fps"]:
            rep.error("timeline", f"scene {s['id']} is shorter than 0.5s")
    if sum(s["durationInFrames"] for s in rc["scenes"]) != rc["durationInFrames"]:
        rep.error("timeline", "scene durations do not add up to the film's length")
    vo_path = ws.vo_dir / "manifest.json"
    vo = json.loads(vo_path.read_text()) if vo_path.exists() else {"lines": []}
    rep.extend(check_narration(vo, rc))
    am_path = ws.root / "build" / "audio-manifest.json"
    pol = rc.get("audioPolicy") or {"mode": "voiceover", "voiceover": True, "soundEffects": True, "music": False}
    if am_path.exists():
        am = json.loads(am_path.read_text())
        rep.extend(check_no_music(am, ws.master_audio, rc))
        # The master is not what ships: prove the encoded films too.
        for aspect, path in videos.items():
            if pol["mode"] != "silent" and path.is_file() and facts["videos"].get(aspect, {}).get("audio"):
                rep.extend(check_no_music(am, path, rc))
    else:
        rep.error("audio", "no audio manifest; the mix was not built by `promo audio`")
    facts["narrationLines"] = len(vo.get("lines", []))
    facts["voiceEngine"] = vo.get("engine")
    facts["audioPolicy"] = pol
    write_json(ws.qa_dir / "qa.json", {"ok": rep.ok, "issues": [i.__dict__ for i in rep.issues], **facts})
    write_json(ws.qa_dir / "validation.json", validation(rep, facts, rc))
    ws.qa_report.write_text(report_md(rep, facts, rc))
    return rep


CHECKS = [  # id, the Issue.where values that belong to it, what it verifies
    ("render", ("render",), "every requested file exists and is non-empty"),
    ("encoding", None, "resolution, frame rate, duration, decode, black and frozen stretches, audio stream per mode"),
    ("timeline", ("timeline",), "scene timing adds up; no scene under 0.5 s"),
    ("narration", ("narration",), "voice lines match the plan and the audio mode, sit in their scenes, never overlap"),
    ("audio", ("audio",), "mix sources match the audio mode; no music; silence between cues"),
]


def validation(rep: Report, facts: dict, rc: dict) -> dict:
    """Machine-readable result: one status per check, with the messages that decided it."""
    video_names = {Path(f["file"]).name for f in facts["videos"].values()}
    checks = []
    for cid, wheres, what in CHECKS:
        mine = [i for i in rep.issues if (i.where in video_names if wheres is None else i.where in wheres)]
        checks.append({"id": cid, "verifies": what,
                       "status": "FAIL" if any(i.level == "error" for i in mine) else "PASS",
                       "messages": [str(i) for i in mine]})
    return {"result": "PASS" if rep.ok else "FAIL", "product": rc["product"], "source": rc["source"],
            "audioPolicy": facts.get("audioPolicy"), "duration": rc["duration"], "fps": rc["fps"],
            "scenes": len(rc["scenes"]), "checks": checks, "videos": facts["videos"]}


def _rel(p, root: Path | None) -> str:
    """Workspace-relative paths in the report: it is meant to be shared."""
    try:
        return Path(p).resolve().relative_to(root).as_posix() if root else str(p)
    except ValueError:
        return str(p)


def report_md(rep: Report, facts: dict, rc: dict) -> str:
    pol = facts.get("audioPolicy") or {}
    lines = [f"# TEST_REPORT — {rc['product']}", "", f"Result: **{'PASS' if rep.ok else 'FAIL'}** "
             f"({len(rep.errors)} errors, {len(rep.warnings)} warnings)", "", "## Checks", "",
             f"- Audio mode: **{pol.get('mode', '?')}** (voice-over {'on' if pol.get('voiceover') else 'off'}, "
             f"effects {'on' if pol.get('soundEffects') else 'off'}, music never)",
             "- Render produced each requested file; audio stream present for voice-over/effects, absent "
             "(or verified digital silence) for silent",
             "- Resolution, frame rate and duration match render-config.json",
             "- Full decode pass without errors; no black stretch over 1 s; frozen stretches reported",
             "- Scene timing adds up; no scene under 0.5 s",
             "- Narration: every line rendered, inside its scene, no overlaps",
             "- Audio present; mix contains only library effects, voice and (optional) non-melodic ambience",
             "- Near-silence wherever no cue or line is sounding, in the master and in each encoded file: "
             "no background music, no bed, and no speech in effects-only mode",
             "- Two stills per scene exported for visual review (text overflow, layout)", "", "## Files", ""]
    for aspect, f in facts["videos"].items():
        lines.append(f"- {aspect}: `{f['file']}` · {f.get('width')}×{f.get('height')} · {f.get('fps')} fps · "
                     f"{f.get('duration')} s · audio {(f.get('audio') or {}).get('codec', 'none')} · "
                     f"mean {f.get('meanVolume', '?')} dB · {f['bytes'] / 1e6:.1f} MB")
    lines += ["", f"Narration: {facts['narrationLines']} lines via {facts['voiceEngine'] or 'none'}", "",
              "## Issues", ""]
    lines += [f"- {i}" for i in rep.issues] or ["- none"]
    lines += ["", "## Stills for review", ""]
    for aspect, f in facts["videos"].items():
        lines += [f"- {aspect}: `{Path(f['stills'][0]).parent}` ({len(f['stills'])} frames)"] if f.get("stills") else []
    return "\n".join(lines) + "\n"
