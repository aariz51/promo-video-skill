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


ANIMATED = 0.004  # mean |ΔY| between a scene's start, middle and end; camera drift alone is ~0.003
EMPTY = 0.0018  # detail (local high-frequency energy) a scene must reach in at least one sampled frame;
#                bare ground with grain and vignette measures ~0.0011


def check_motion(path: Path, rc: dict) -> tuple[Report, list[dict]]:
    """Every scene animates (its start, middle and end frames differ beyond camera drift)
    and none is empty, measured on the encoded file."""
    from . import reference as R
    r = Report()
    Y = [R._luma(f) for f in R._decode(path, rc["fps"], R.SIG_W, R.SIG_H)]
    rows = []
    for sc in rc["scenes"]:
        a, n = sc["from"], sc["durationInFrames"]
        s0 = min(len(Y) - 1, a + sc["transition"]["frames"] + 2)
        m, e = min(len(Y) - 1, a + n // 2), min(len(Y) - 1, a + n - 3)
        change = max(R._mad(Y[s0], Y[m]), R._mad(Y[m], Y[e]))
        samples = [min(len(Y) - 1, s0 + (e - s0) * k // 4) for k in range(5)]
        most = max(R.detail(Y[k]) for k in samples)
        rows.append({"scene": sc["id"], "change": round(change, 4), "detail": round(most, 5),
                     "frames": [round(x / rc["fps"], 2) for x in (s0, m, e)]})
        if change < ANIMATED:
            r.error("motion", f"scene '{sc['id']}' barely changes between its start, middle and end "
                    f"({change:.4f}); a scene needs a purposeful animation")
        if most < EMPTY:
            r.error("motion", f"scene '{sc['id']}' never shows any content (detail {most:.4f})")
    return r, rows


EDGE = 45  # 8-bit luma: an edge pixel this far from the film's ground colour is content touching the edge


def check_edges(path: Path, rc: dict, width: int, height: int) -> Report:
    """Warn when bright content touches the frame edge mid-scene: usually a device or card
    cropped by its camera move. A warning, because some designs bleed off-frame on purpose."""
    r = Report()
    g = rc.get("style", {}).get("ground", "#0B0C0F").lstrip("#")
    ground = round(0.299 * int(g[0:2], 16) + 0.587 * int(g[2:4], 16) + 0.114 * int(g[4:6], 16))
    for sc in rc["scenes"]:
        for frac in (0.5, 0.9):
            t = (sc["from"] + sc["durationInFrames"] * frac) / rc["fps"]
            raw = run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                       "-pix_fmt", "gray", "-f", "rawvideo", "-"], text=False).stdout
            if len(raw) != width * height:
                continue
            cols = (0, 1, width - 2, width - 1)
            side = max(max(abs(raw[y * width + x] - ground) for x in cols) for y in range(0, height, 4))
            rows = (0, height - 1)
            top = max(max(abs(raw[y * width + x] - ground) for y in rows) for x in range(0, width, 4))
            if max(side, top) >= EDGE:
                r.warn(path.name, f"scene '{sc['id']}' at {t:.1f}s: content touches the frame edge; "
                       "look at it (a cropped device or card?)")
                break
    return r


def check_transitions(path: Path, rc: dict) -> tuple[Report, list[dict]]:
    from . import reference as R
    r = Report()
    rows = R.verify_transitions(path, rc)
    for row in rows:
        if not row["ok"]:
            r.error("transitions", f"into '{row['scene']}' at {row.get('at', '?')}s: planned {row['planned']}, "
                    f"the file shows {row['observed']}")
    return r, rows


def check_reference(rows: list[dict], rc: dict, bd: dict) -> tuple[Report, list[dict]]:
    """Mode B: each measured reference transition is realised by the film, as measured in it."""
    r = Report()
    observed = {row["scene"]: row for row in rows}
    out = []
    for sc in rc["scenes"]:
        refs = sc.get("ref")
        refs = [refs] if isinstance(refs, str) else list(refs or [])
        tr = next((t for t in bd["transitions"] if refs and t["to"] == refs[0]), None)
        if not tr:
            continue
        got = observed.get(sc["id"])
        row = {"reference": tr["id"], "measured": tr["type"], "scene": sc["id"],
               "planned": sc["transition"]["type"], "observed": got["observed"] if got else "—",
               "deviation": sc.get("deviation"), "ok": bool(got and got["ok"])}
        out.append(row)
        if not row["ok"] and not row["deviation"]:
            r.error("reference", f"reference {tr['id']} ({tr['type']}) into '{sc['id']}' is not visible in the film "
                    f"(observed: {row['observed']})")
    return r, out


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
        mr, f["motion"] = check_motion(path, rc)
        if f.get("width"):
            rep.extend(check_edges(path, rc, f["width"], f["height"]))
        tr, f["transitions"] = check_transitions(path, rc)
        rep.extend(mr)
        rep.extend(tr)
        bd_path = ws.reference_dir / "breakdown.json"
        if rc.get("source") in ("reference", "inspiration") and bd_path.exists() and "reference" not in facts:
            rr, facts["reference"] = check_reference(f["transitions"], rc, read_json(bd_path))
            rep.extend(rr)
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
    ("motion", ("motion",), "every scene animates between its start, middle and end, and none is empty"),
    ("transitions", ("transitions",), "each planned transition is measured in the file where the plan puts it"),
    ("reference", ("reference",), "Mode B: every measured reference transition is visible in the film"),
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
    if not facts.get("reference"):
        checks = [c for c in checks if c["id"] != "reference"]  # autonomous films have no reference
    return {"result": "PASS" if rep.ok else "FAIL", "product": rc["product"], "source": rc["source"],
            "reference": facts.get("reference"),
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
             "- Every scene animates (start / middle / end frames differ beyond camera drift) and none is empty",
             "- Each planned transition is measured in the encoded file at its planned time (cut, fade, wipe "
             "direction, dip colour)",
             "- Mode B: every measured reference transition is visible in the film",
             "- Two stills per scene exported for visual review (text overflow, layout)", "", "## Files", ""]
    for aspect, f in facts["videos"].items():
        lines.append(f"- {aspect}: `{f['file']}` · {f.get('width')}×{f.get('height')} · {f.get('fps')} fps · "
                     f"{f.get('duration')} s · audio {(f.get('audio') or {}).get('codec', 'none')} · "
                     f"mean {f.get('meanVolume', '?')} dB · {f['bytes'] / 1e6:.1f} MB")
    for aspect, f in facts["videos"].items():
        if f.get("transitions"):
            lines += ["", f"### Transitions measured in the {aspect} file", "", "| Into | At | Planned | Observed | OK |",
                      "|---|---|---|---|---|"]
            lines += [f"| {t['scene']} | {t.get('at', '?')} s | {t['planned']} | {t['observed']} | "
                      f"{'yes' if t['ok'] else '**no**'} |" for t in f["transitions"]]
        break
    if facts.get("reference"):
        lines += ["", "### Reference transitions in the film", "", "| Reference | Measured | Scene | Observed | OK |",
                  "|---|---|---|---|---|"]
        lines += [f"| {x['reference']} | {x['measured']} | {x['scene']} | {x['observed']} | "
                  f"{'yes' if x['ok'] else ('deviation' if x['deviation'] else '**no**')} |" for x in facts["reference"]]
    lines += ["", f"Narration: {facts['narrationLines']} lines via {facts['voiceEngine'] or 'none'}", "",
              "## Issues", ""]
    lines += [f"- {i}" for i in rep.issues] or ["- none"]
    lines += ["", "## Stills for review", ""]
    for aspect, f in facts["videos"].items():
        lines += [f"- {aspect}: `{Path(f['stills'][0]).parent}` ({len(f['stills'])} frames)"] if f.get("stills") else []
    return "\n".join(lines) + "\n"
