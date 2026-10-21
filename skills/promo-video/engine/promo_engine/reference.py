"""Reference analysis: measure the reference video itself, then hand the agent evidence.

`watch` (claude-video) supplies the transcript and a first set of frames. This module adds
what a creative breakdown needs and `watch` does not measure, all from the decoded pixels:

  metadata      duration, fps, size, aspect, audio, codec (ffprobe on the actual file)
  boundaries    hard cuts, flashes, and gradual transitions classified from the signal:
                dissolve (frames are a linear blend of both sides), dip to black / white,
                wipe (a moving partition, with its direction), or `gradual` when none fits
  scenes        start / end / duration, motion energy, a camera estimate from aligning the
                scene's first and last frames (static, pan, tilt, push-in, pull-out), mean
                colour, brightness and a three-colour palette
  evidence      JPEG frames at each scene's start / middle / end and either side of each
                transition, uniform samples across the whole film, and timestamped
                contact sheets of all of them
  motion spec   pacing, shot-length distribution, cut density by quarter, transition and
                camera vocabularies, opening and ending conventions

Everything lands in `<workspace>/reference/` with `breakdown.json` as the index. Results
are cached by a fingerprint of the file's bytes and the analysis parameters. Measured
values are labelled as measurements; what they cannot tell (typography, what is on screen,
why) is left for the agent to write from the frames, in CREATIVE_DIRECTION.md.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
from fractions import Fraction
from pathlib import Path

from .util import PromoError, fmt_time, read_json, require_tools, run, write_json

VERSION = 1
SIG_W, SIG_H = 64, 36  # analysis signal
MAX_SIGNAL_FRAMES = 4000
CUT_T = 0.10  # mean |ΔY| (0–1) that counts as a hard cut when isolated
GRAD_T = 0.006  # per-frame change that keeps a gradual run alive
CHANGE_T = 0.05  # content change across a run that makes it a transition, not motion
DARK, LIGHT = 0.07, 0.93
FLASH_MAX = 0.2  # seconds: a scene shorter than this between two cuts is a flash
EVIDENCE_W = 640
SHEET_COLS, CELL_W = 4, 320


# ── metadata ──────────────────────────────────────────────────────────────────────

def _ratio_name(w: int, h: int) -> str:
    r = Fraction(w, h).limit_denominator(32)
    named = {(16, 9): "16:9", (9, 16): "9:16", (1, 1): "1:1", (4, 3): "4:3", (3, 4): "3:4", (4, 5): "4:5",
             (21, 9): "21:9", (2, 1): "2:1", (1, 2): "1:2"}
    best = min(named, key=lambda k: abs(k[0] / k[1] - w / h))
    return named[best] if abs(best[0] / best[1] - w / h) < 0.02 else f"{r.numerator}:{r.denominator}"


def probe(video: str | Path) -> dict:
    require_tools("ffmpeg", "ffprobe")
    res = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)], check=False)
    if res.returncode != 0:
        raise PromoError(f"the reference cannot be read: {Path(video).name}", hint="is it a complete video file?")
    info = json.loads(res.stdout or "{}")
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        raise PromoError(f"the reference has no video stream: {Path(video).name}")
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float((info.get("format") or {}).get("duration") or v.get("duration") or 0)
    if dur <= 0:
        raise PromoError("the reference has no measurable duration (truncated or still image?)")
    num, den = (int(x) for x in (v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1").split("/"))
    fps = num / den if den else 0.0
    if not fps:
        num, den = (int(x) for x in v.get("r_frame_rate", "0/1").split("/"))
        fps = num / den if den else 0.0
    w, h = int(v["width"]), int(v["height"])
    return {"duration": round(dur, 3), "fps": round(fps, 3), "width": w, "height": h,
            "aspect": _ratio_name(w, h), "videoCodec": v.get("codec_name"),
            "audio": {"present": bool(a), "codec": a.get("codec_name") if a else None,
                      "channels": a.get("channels") if a else None},
            "estimatedFrames": int(round(dur * fps)) if fps else None}


# ── signal ────────────────────────────────────────────────────────────────────────

def _decode(video: Path, fps: float, w: int, h: int) -> list[bytes]:
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf", f"fps={fps},scale={w}:{h}:flags=area", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    res = subprocess.run(cmd, capture_output=True)
    size = w * h * 3
    raw = res.stdout
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    if res.returncode != 0 and not frames:
        tail = res.stderr.decode(errors="replace").strip().splitlines()[-3:]
        raise PromoError("the reference could not be decoded:\n  " + "\n  ".join(tail))
    return frames


def _frame_at(video: Path, t: float, w: int, h: int) -> bytes | None:
    res = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
                          "-an", "-vf", f"scale={w}:{h}:flags=area", "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                         capture_output=True)
    return res.stdout if len(res.stdout) == w * h * 3 else None


def _luma(rgb: bytes) -> list[float]:
    return [(rgb[i] * 299 + rgb[i + 1] * 587 + rgb[i + 2] * 114) / 255000 for i in range(0, len(rgb), 3)]


def _mad(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _downsample(y: list[float], w: int, h: int, tw: int, th: int) -> list[float]:
    fx, fy = w // tw, h // th
    out = []
    for r in range(th):
        for c in range(tw):
            s = 0.0
            for yy in range(r * fy, r * fy + fy):
                base = yy * w + c * fx
                s += sum(y[base:base + fx])
            out.append(s / (fx * fy))
    return out


def _err(a: list[float], b: list[float], w: int, h: int, dx: float, dy: float, scale: float) -> float | None:
    cx, cy = (w - 1) / 2, (h - 1) / 2
    err, n = 0.0, 0
    for r in range(h):
        sy = round((r - cy - dy) / scale + cy)
        if not 0 <= sy < h:
            continue
        row_b, row_a = r * w, sy * w
        for c in range(w):
            sx = round((c - cx - dx) / scale + cx)
            if 0 <= sx < w:
                err += abs(b[row_b + c] - a[row_a + sx])
                n += 1
    return err / n if n >= w * h * 0.45 else None


SCALES = (0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.18, 1.25)
# A motion prior far below the error a real one-pixel move removes (~0.02 on textured
# frames): on axes the picture cannot resolve (vertical bars, flat sky) the smaller move wins.
SHIFT_COST, SCALE_COST = 0.0004, 0.01


def _cost(err: float | None, dx: float, dy: float, sc: float) -> float | None:
    return None if err is None else err + SHIFT_COST * (abs(dx) + abs(dy)) + SCALE_COST * abs(sc - 1.0) / 0.05


def align(a: list[float], b: list[float], w: int = SIG_W, h: int = SIG_H) -> dict:
    """Best similarity transform mapping frame `a` onto frame `b`.

    Coarse search at half resolution (shift, then scale around the best shift), refined
    at full resolution. Returns shift as a fraction of the frame (+dx: content moved right),
    scale (>1: content grew, i.e. push-in), the remaining error and the error without any
    transform. Doing nothing wins ties, so flat or unchanged frames report no motion."""
    ident = _mad(a, b)
    best = (ident, 0.0, 0.0, 1.0)

    best_cost = ident

    def consider(err, dx, dy, sc):
        nonlocal best, best_cost
        c = _cost(err, dx, dy, sc)
        if c is not None and c < best_cost - 1e-9 and err < ident * 0.7 and ident - err > 0.003:
            best, best_cost = (err, dx, dy, sc), c

    cw, ch = w // 2, h // 2
    ca, cb = _downsample(a, w, h, cw, ch), _downsample(b, w, h, cw, ch)
    coarse = (_mad(ca, cb), 0, 0, 1.0)
    for dy in range(-4, 5):
        for dx in range(-6, 7):
            e = _cost(_err(ca, cb, cw, ch, dx, dy, 1.0), 2 * dx, 2 * dy, 1.0)
            if e is not None and e < coarse[0] - 1e-9:
                coarse = (e, dx, dy, 1.0)
    base = coarse
    for sc in SCALES:
        for ddy in (-1, 0, 1):
            for ddx in (-1, 0, 1):
                dx, dy = base[1] + ddx, base[2] + ddy
                e = _cost(_err(ca, cb, cw, ch, dx, dy, sc), 2 * dx, 2 * dy, sc)
                if e is not None and e < coarse[0] - 1e-9:
                    coarse = (e, dx, dy, sc)
    _, cdx, cdy, csc = coarse
    i = SCALES.index(csc)
    for sc in SCALES[max(0, i - 1):i + 2]:
        for ddy in (-1, 0, 1):
            for ddx in (-1, 0, 1):
                dx, dy = cdx * 2 + ddx, cdy * 2 + ddy
                consider(_err(a, b, w, h, dx, dy, sc), dx, dy, sc)
    return {"dx": round(best[1] / w, 3), "dy": round(best[2] / h, 3), "scale": best[3],
            "error": round(best[0], 4), "unaligned": round(ident, 4)}


# ── boundary detection and classification ─────────────────────────────────────────

def _classify_run(Y: list[list[float]], pre: int, post: int) -> tuple[str, dict]:
    """What happened between frame `pre` and frame `post` (exclusive run in between)."""
    ys, ye = Y[pre], Y[post]
    lum = [sum(Y[k]) / len(Y[k]) for k in range(pre, post + 1)]
    lo, hi = min(lum[1:-1] or lum), max(lum[1:-1] or lum)
    ends_lo, ends_hi = min(lum[0], lum[-1]), max(lum[0], lum[-1])
    if lo < DARK and ends_lo > lo + 0.06:
        return "dip-black", {"minLuma": round(lo, 3)}
    if hi > LIGHT and ends_hi < hi - 0.06:
        return "dip-white", {"maxLuma": round(hi, 3)}
    # Dissolve: each inner frame ≈ (1-α)·start + α·end, with α rising.
    diff = [e - s for s, e in zip(ys, ye)]
    norm = sum(d * d for d in diff)
    if norm > 0 and post - pre >= 2:
        alphas, resid = [], []
        for k in range(pre + 1, post):
            yk = Y[k]
            alpha = sum((x - s) * d for x, s, d in zip(yk, ys, diff)) / norm
            alphas.append(alpha)
            resid.append(sum(abs(x - (s + alpha * d)) for x, s, d in zip(yk, ys, diff)) / len(yk))
        rising = all(b >= a - 0.08 for a, b in zip(alphas, alphas[1:]))
        if rising and statistics.fmean(resid) < 0.02 and alphas[0] < 0.6 and alphas[-1] > 0.4:
            return "dissolve", {"alpha": [round(a, 2) for a in alphas], "residual": round(statistics.fmean(resid), 4)}
    # Wipe: each inner frame splits into a part that matches the end and a part that
    # matches the start, and the split moves monotonically across the frame.
    for axis in ("x", "y"):
        n_lines = SIG_W if axis == "x" else SIG_H
        fracs, sides = [], []
        for k in range(pre + 1, post):
            yk, labels = Y[k], []
            for i in range(n_lines):
                idx = [r * SIG_W + i for r in range(SIG_H)] if axis == "x" else list(range(i * SIG_W, i * SIG_W + SIG_W))
                ds = sum(abs(yk[j] - ys[j]) for j in idx)
                de = sum(abs(yk[j] - ye[j]) for j in idx)
                labels.append(de < ds)
            changes = sum(1 for a, b in zip(labels, labels[1:]) if a != b)
            fracs.append(sum(labels) / n_lines)
            if changes <= 2:
                sides.append("lead" if labels[0] and not labels[-1] else "trail" if labels[-1] and not labels[0] else None)
            else:
                sides.append("mixed")
        partial = [f for f in fracs if 0.08 < f < 0.92]
        if partial and all(s in ("lead", "trail", None) for s in sides) and \
                all(b >= a - 0.05 for a, b in zip(fracs, fracs[1:])):
            known = [s for s in sides if s in ("lead", "trail")]
            if known and all(s == known[0] for s in known):
                # "lead": the new picture covers the left/top first, so the edge travels right/down.
                d = {("x", "lead"): "right", ("x", "trail"): "left", ("y", "lead"): "down", ("y", "trail"): "up"}
                return f"wipe-{d[(axis, known[0])]}", {"coverage": [round(f, 2) for f in fracs]}
    return "gradual", {}


def camera_move(Y: list[list[float]], pre: int, post: int, fps: float) -> bool:
    """True when short steps across the run are each explained by one shift/scale: the
    camera (or the whole frame) moved, and the content did not cut or blend."""
    step = max(1, round(0.12 * fps))
    pairs = list(range(pre, post - step + 1, step)) or [pre]
    if len(pairs) > 12:
        pairs = pairs[:: math.ceil(len(pairs) / 12)]
    explained = 0
    for k in pairs:
        al = align(Y[k], Y[min(post, k + step)])
        moved = al["scale"] != 1.0 or al["dx"] or al["dy"]
        if al["unaligned"] < 0.004 or (moved and al["error"] < 0.5 * al["unaligned"]):
            explained += 1
    return explained >= 0.7 * len(pairs)


def track_camera(Y: list[list[float]], idx: list[int], fps: float) -> dict:
    """Accumulate short-step alignments across a scene: total pan / tilt (fractions of the
    frame, may exceed 1 for long pans), total scale, and how many steps one transform
    explained. Long moves exceed what a single first-vs-last alignment can resolve."""
    step = max(1, round(0.12 * fps), math.ceil(len(idx) / 24))
    picks = idx[::step]
    if picks and picks[-1] != idx[-1]:
        picks.append(idx[-1])
    dx = dy = 0.0
    scale = 1.0
    explained = changed = 0
    for a_i, b_i in zip(picks, picks[1:]):
        al = align(Y[a_i], Y[b_i])
        if al["unaligned"] < 0.004:
            continue
        changed += 1
        if al["error"] < 0.5 * al["unaligned"]:
            explained += 1
            dx += al["dx"]
            dy += al["dy"]
            scale *= al["scale"]
    return {"dx": round(dx, 3), "dy": round(dy, 3), "scale": round(scale, 3), "steps": max(0, len(picks) - 1),
            "changedSteps": changed, "explainedSteps": explained}


def detect(Y: list[list[float]], times: list[float]) -> dict:
    """Cuts and gradual transitions from the luma signal; opening/closing fades."""
    n = len(Y)
    d = [0.0] + [_mad(Y[i], Y[i - 1]) for i in range(1, n)]
    events: list[dict] = []
    is_cut = [False] * n
    for i in range(1, n):
        win = [d[j] for j in range(max(1, i - 5), min(n, i + 6)) if j != i]
        med = statistics.median(win) if win else 0.0
        neigh = max(d[i - 1] if i > 1 else 0.0, d[i + 1] if i + 1 < n else 0.0)
        if d[i] > max(CUT_T, 4 * med) and d[i] > 2 * neigh:
            is_cut[i] = True
            events.append({"type": "cut", "i0": i - 1, "i1": i, "score": round(d[i], 3)})
    # Gradual runs: consecutive elevated frames, split at cuts.
    i = 1
    opening = closing = None
    while i < n:
        if d[i] > GRAD_T and not is_cut[i]:
            j = i
            while j + 1 < n and d[j + 1] > GRAD_T and not is_cut[j + 1]:
                j += 1
            pre, post = i - 1, j
            if post - pre >= 2 and _mad(Y[pre], Y[post]) > CHANGE_T:
                lum_pre = sum(Y[pre]) / len(Y[pre])
                lum_post = sum(Y[post]) / len(Y[post])
                dark_before = all(sum(Y[k]) / len(Y[k]) < DARK for k in range(0, pre + 1))
                dark_after = all(sum(Y[k]) / len(Y[k]) < DARK for k in range(post, n))
                if dark_before and not events:
                    opening = {"type": "fade-in", "from": "black", "start": 0.0, "end": times[post]}
                elif dark_after:
                    closing = {"type": "fade-out", "to": "black", "start": times[pre], "end": times[n - 1]}
                else:
                    kind, detail = _classify_run(Y, pre, post)
                    fps = 1 / (times[1] - times[0]) if len(times) > 1 else 25
                    if kind == "gradual" and camera_move(Y, pre, post, fps):
                        pass  # the camera moved inside one scene; not a boundary
                    else:
                        events.append({"type": kind, "i0": pre, "i1": post, "detail": detail})
            i = j + 1
        else:
            i += 1
    events.sort(key=lambda e: e["i0"])
    lum = [sum(y) / len(y) for y in Y]
    merged: list[dict] = []
    for e in events:
        prev = merged[-1] if merged else None
        if prev and prev["type"] != "cut" and e["type"] != "cut" and \
                times[e["i0"]] - times[prev["i1"]] <= 0.3:
            gap = lum[prev["i1"]:e["i0"] + 1]
            if gap and max(gap) < DARK:
                merged[-1] = {"type": "dip-black", "i0": prev["i0"], "i1": e["i1"], "detail": {"minLuma": round(min(gap), 3)}}
                continue
            if gap and min(gap) > LIGHT:
                merged[-1] = {"type": "dip-white", "i0": prev["i0"], "i1": e["i1"], "detail": {"maxLuma": round(max(gap), 3)}}
                continue
        merged.append(e)
    events = merged
    # A gradual run never swallows a neighbouring cut: clip it to the frames between them.
    clean: list[dict] = []
    for e in events:
        if clean and e["i0"] < clean[-1]["i1"]:
            if e["type"] == "cut":
                clean[-1]["i1"] = min(clean[-1]["i1"], e["i0"])
            else:
                e["i0"] = clean[-1]["i1"]
            if e["i1"] <= e["i0"] and e["type"] != "cut":
                continue
        clean.append(e)
    events = [e for e in clean if e["type"] == "cut" or e["i1"] > e["i0"]]
    return {"events": events, "diff": d, "opening": opening, "closing": closing}


# ── scenes, measures, evidence ────────────────────────────────────────────────────

def _hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


def _colour(frames: list[bytes]) -> dict:
    sums = [0.0, 0.0, 0.0]
    bins: dict[tuple, int] = {}
    count = 0
    for fr in frames:
        for i in range(0, len(fr), 3):
            r, g, b = fr[i], fr[i + 1], fr[i + 2]
            sums[0] += r
            sums[1] += g
            sums[2] += b
            key = (r >> 5, g >> 5, b >> 5)
            bins[key] = bins.get(key, 0) + 1
            count += 1
    mean = tuple(s / count for s in sums)
    top = sorted(bins.items(), key=lambda kv: -kv[1])[:3]
    palette = [{"hex": _hex(tuple(c * 32 + 16 for c in k)), "share": round(v / count, 2)} for k, v in top]
    return {"mean": _hex(mean), "palette": palette}


def _camera_label(al: dict, energy: float) -> str:
    if al["changedSteps"] and al["explainedSteps"] < 0.6 * al["changedSteps"] and energy > 0.01:
        return "internal motion (subject or UI moves; no single camera move explains it)"
    parts = []
    if al["scale"] >= 1.05:
        parts.append(f"push-in (content ×{al['scale']:.2f})")
    elif 0 < al["scale"] <= 0.95:
        parts.append(f"pull-out (content ×{al['scale']:.2f})")
    if abs(al["dx"]) >= 0.06:
        parts.append(f"pan: content moves {'right' if al['dx'] > 0 else 'left'} {abs(al['dx']) * 100:.0f}% of width")
    if abs(al["dy"]) >= 0.06:
        parts.append(f"tilt: content moves {'down' if al['dy'] > 0 else 'up'} {abs(al['dy']) * 100:.0f}% of height")
    if parts:
        return "; ".join(parts)
    return "static hold" if energy < 0.004 else "subtle movement (below camera-estimate resolution)"


def _sheet_font() -> dict[str, list[str]]:
    rows = {
        "0": "111 101 101 101 111", "1": "010 110 010 010 111", "2": "111 001 111 100 111",
        "3": "111 001 111 001 111", "4": "101 101 111 001 001", "5": "111 100 111 001 111",
        "6": "111 100 111 101 111", "7": "111 001 001 001 001", "8": "111 101 111 101 111",
        "9": "111 101 111 001 111", ":": "000 010 000 010 000", ".": "000 000 000 000 010",
        "-": "000 000 111 000 000", "S": "111 100 111 001 111", "T": "111 010 010 010 010",
        "U": "101 101 101 101 111", " ": "000 000 000 000 000", "M": "101 111 111 101 101",
        "E": "111 100 111 100 111", "A": "111 101 111 101 101", "B": "110 101 110 101 110",
    }
    return {k: v.split() for k, v in rows.items()}


FONT = _sheet_font()


def _stamp(buf: bytearray, w: int, x0: int, y0: int, text: str, scale: int = 3) -> None:
    """Draw `text` (FONT glyphs) white on a black box into an RGB buffer."""
    tw = len(text) * 4 * scale + scale
    th = 7 * scale
    h = len(buf) // (w * 3)
    for y in range(y0, min(h, y0 + th)):
        for x in range(x0, min(w, x0 + tw)):
            p = (y * w + x) * 3
            buf[p:p + 3] = b"\x00\x00\x00"
    for ci, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[" "])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        x = x0 + scale + ci * 4 * scale + gx * scale + sx
                        y = y0 + scale + gy * scale + sy
                        if x < w and y < h:
                            p = (y * w + x) * 3
                            buf[p:p + 3] = b"\xff\xff\xff"


def contact_sheet(video: Path, cells: list[tuple[float, str]], dest: Path, src_w: int, src_h: int) -> Path:
    """A grid of frames at the given times, each stamped with its label and timestamp."""
    cw = CELL_W
    ch = max(2, round(cw * src_h / src_w / 2) * 2)
    rows = math.ceil(len(cells) / SHEET_COLS)
    W, H = cw * SHEET_COLS, ch * rows
    sheet = bytearray(W * H * 3)
    for k, (t, label) in enumerate(cells):
        raw = _frame_at(video, t, cw, ch)
        if raw is None:
            raise PromoError(f"no frame could be decoded at {fmt_time(t)} for the contact sheet")
        cell = bytearray(raw)
        _stamp(cell, cw, 4, 4, f"{label} {fmt_time(t)}")
        r, c = divmod(k, SHEET_COLS)
        for y in range(ch):
            src = y * cw * 3
            dst = ((r * ch + y) * W + c * cw) * 3
            sheet[dst:dst + cw * 3] = cell[src:src + cw * 3]
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-i", "-", "-frames:v", "1", "-q:v", "3", str(dest)], input=bytes(sheet), capture_output=True)
    if proc.returncode != 0 or not dest.is_file():
        raise PromoError(f"could not write contact sheet {dest.name}")
    return dest


def extract_frame(video: Path, t: float, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0.0, t):.3f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"scale='min({EVIDENCE_W},iw)':-2", "-q:v", "3", str(dest)])
    if not dest.is_file() or dest.stat().st_size == 0:
        raise PromoError(f"no frame could be extracted at {fmt_time(t)}")
    return dest


def fingerprint(video: Path, params: dict) -> str:
    h = hashlib.sha256()
    with open(video, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    # The analyzer's own source is an input too: changed detection logic must not be served stale results.
    h.update(Path(__file__).read_bytes())
    h.update(json.dumps([VERSION, params], sort_keys=True).encode())
    return h.hexdigest()[:24]


def _fname(t: float) -> str:
    return f"{t:07.2f}".replace(".", "_")


def analyze(video: str | Path, out_dir: str | Path, *, transcript: dict | None = None,
            source: str | None = None, force: bool = False) -> dict:
    """Measure the reference and write `<out_dir>/breakdown.json` plus its evidence."""
    video = Path(video)
    out = Path(out_dir)
    if not video.is_file():
        raise PromoError(f"reference video not found: {video}")
    meta = probe(video)
    fps_a = meta["fps"] or 25.0
    if meta["duration"] * fps_a > MAX_SIGNAL_FRAMES:
        fps_a = max(4.0, MAX_SIGNAL_FRAMES / meta["duration"])
    fps_a = round(fps_a, 3)
    params = {"fps": fps_a, "sig": [SIG_W, SIG_H], "cut": CUT_T, "grad": GRAD_T, "change": CHANGE_T}
    fp = fingerprint(video, params)
    index = out / "breakdown.json"
    if index.exists() and not force:
        old = read_json(index)
        if old.get("fingerprint") == fp and all((out / f["file"]).is_file() for f in _all_frames(old)):
            old["cached"] = True
            return old

    frames = _decode(video, fps_a, SIG_W, SIG_H)
    decoded = len(frames) / fps_a
    if not frames or decoded < meta["duration"] * 0.85 - 0.5:
        raise PromoError(f"only {decoded:.1f}s of the reference's {meta['duration']:.1f}s could be decoded",
                         hint="the file looks truncated or damaged; re-download or re-export it")
    times = [round(i / fps_a, 3) for i in range(len(frames))]
    duration = meta["duration"]
    Y = [_luma(f) for f in frames]
    det = detect(Y, times)

    # Boundaries → transitions with times; merge flashes (two cuts around a tiny scene).
    trans: list[dict] = []
    for e in det["events"]:
        if e["type"] == "cut":
            t = times[e["i1"]]
            trans.append({"type": "cut", "start": t, "end": t, "detail": {"score": e["score"]}})
        else:
            trans.append({"type": e["type"], "start": times[e["i0"]], "end": times[e["i1"]], "detail": e["detail"]})
    merged: list[dict] = []
    for tr in trans:
        if merged and merged[-1]["type"] in ("cut", "flash") and tr["type"] == "cut" and tr["start"] - merged[-1]["end"] <= FLASH_MAX:
            merged[-1] = {"type": "flash", "start": merged[-1]["start"], "end": tr["end"], "detail": {"frames": "flash cut"}}
        else:
            merged.append(tr)
    trans = [t for t in merged if 0 < t["start"] < duration and t["end"] <= duration]

    scenes: list[dict] = []
    cursor = 0.0
    for k, tr in enumerate(trans + [None]):
        end = tr["start"] if tr else duration
        scenes.append({"id": f"S{len(scenes) + 1:02d}", "start": round(cursor, 3), "end": round(end, 3),
                       "duration": round(end - cursor, 3)})
        if tr:
            cursor = tr["end"]
    for k, tr in enumerate(trans):
        tr["id"] = f"T{k + 1:02d}"
        tr["from"], tr["to"] = scenes[k]["id"], scenes[k + 1]["id"]
        tr["duration"] = round(tr["end"] - tr["start"], 3)

    # Per-scene measurements from the signal.
    op, cl = det["opening"], det["closing"]
    for sc in scenes:
        # Measure the picture, not the opening/closing fade (recorded separately).
        lo = max(sc["start"], op["end"] if op else 0.0) + 0.04
        hi = min(sc["end"], cl["start"] if cl else sc["end"]) - 0.04
        idx = [i for i, t in enumerate(times) if lo <= t <= hi] or \
              [min(range(len(times)), key=lambda i: abs(times[i] - (sc["start"] + sc["end"]) / 2))]
        energy = statistics.fmean(det["diff"][i] for i in idx[1:]) if len(idx) > 1 else 0.0
        al = track_camera(Y, idx, fps_a)
        sample = [frames[i] for i in idx[:: max(1, len(idx) // 6)]]
        fades = []
        if op and op["end"] > sc["start"] and sc is scenes[0]:
            fades.append(f"fades in from black over {op['end'] - op['start']:.2f}s")
        if cl and cl["start"] < sc["end"] and sc is scenes[-1]:
            fades.append(f"fades out to black from {cl['start']:.2f}s")
        sc["measured"] = {
            "fade": "; ".join(fades) or None,
            "motionEnergy": round(energy, 4),
            "camera": _camera_label(al, energy),
            "cameraEstimate": al,
            "brightness": round(statistics.fmean(sum(Y[i]) / len(Y[i]) for i in idx), 3),
            **_colour(sample),
        }

    # Evidence frames.
    fdir = out / "frames"
    if fdir.exists():
        for old in fdir.glob("*.jpg"):
            old.unlink()
    eps = min(0.1, 0.5 / fps_a + 0.02)
    for sc in scenes:
        pts = {"start": sc["start"] + eps, "mid": (sc["start"] + sc["end"]) / 2, "end": sc["end"] - eps}
        if sc["duration"] < 3 * eps:
            pts = {"mid": (sc["start"] + sc["end"]) / 2}
        sc["frames"] = []
        for tag, t in pts.items():
            t = min(max(0.0, t), duration - 0.05)
            f = extract_frame(video, t, fdir / f"{sc['id']}-{tag}-t{_fname(t)}.jpg")
            sc["frames"].append({"t": round(t, 3), "role": tag, "file": f.relative_to(out).as_posix()})
    for tr in trans:
        pts = {"before": tr["start"] - eps, "during": (tr["start"] + tr["end"]) / 2, "after": tr["end"] + eps}
        if tr["type"] == "cut":
            pts.pop("during")
        tr["frames"] = []
        for tag, t in pts.items():
            t = min(max(0.0, t), duration - 0.05)
            f = extract_frame(video, t, fdir / f"{tr['id']}-{tag}-t{_fname(t)}.jpg")
            tr["frames"].append({"t": round(t, 3), "role": tag, "file": f.relative_to(out).as_posix()})
    n_uniform = max(8, min(48, int(duration // 2)))
    uniform = []
    for k in range(n_uniform):
        t = round(duration * (k + 0.5) / n_uniform, 3)
        f = extract_frame(video, t, fdir / f"U{k + 1:02d}-t{_fname(t)}.jpg")
        uniform.append({"t": t, "file": f.relative_to(out).as_posix()})

    # Contact sheets: scenes (mid frames), transitions (before/after), uniform samples.
    sdir = out / "sheets"
    if sdir.exists():
        for old in sdir.glob("*.jpg"):
            old.unlink()
    sheets = []
    groups = [("scenes", [(f["t"], sc["id"]) for sc in scenes for f in sc["frames"] if f["role"] == "mid"]),
              ("transitions", [(f["t"], tr["id"]) for tr in trans for f in tr["frames"]]),
              ("uniform", [(u["t"], f"U{i + 1:02d}") for i, u in enumerate(uniform)])]
    for name, cells in groups:
        for page in range(0, len(cells), 16):
            chunk = cells[page:page + 16]
            dest = sdir / f"{name}-{page // 16 + 1:02d}.jpg"
            contact_sheet(video, chunk, dest, meta["width"], meta["height"])
            sheets.append({"file": dest.relative_to(out).as_posix(), "kind": name,
                           "cells": [{"label": lab, "t": t} for t, lab in chunk]})

    bd = {
        "version": VERSION,
        "source": source or str(video),
        "video": str(video),
        "fingerprint": fp,
        "analysis": {**params, "decodedSeconds": round(decoded, 2), "frames": len(frames)},
        "metadata": {**meta, "captions": _captions(transcript)},
        "scenes": scenes,
        "transitions": trans,
        "conventions": {"opening": det["opening"], "closing": det["closing"]},
        "uniform": uniform,
        "contactSheets": sheets,
        "motionSpec": motion_spec(scenes, trans, duration, det),
        "cached": False,
    }
    rep = validate(bd, out)
    if rep:
        raise PromoError("the reference analysis is incomplete:\n  " + "\n  ".join(rep))
    write_json(index, bd)
    write_json(out / "motion-spec.json", bd["motionSpec"])
    return bd


def _captions(transcript: dict | None) -> dict:
    if not transcript:
        return {"available": False, "source": "not inspected (no watch transcript)"}
    return {"available": bool(transcript.get("available")), "source": transcript.get("source"),
            "lines": len(transcript.get("lines") or [])}


def _all_frames(bd: dict) -> list[dict]:
    out = [f for sc in bd.get("scenes", []) for f in sc.get("frames", [])]
    out += [f for tr in bd.get("transitions", []) for f in tr.get("frames", [])]
    out += list(bd.get("uniform", [])) + list(bd.get("contactSheets", []))
    return out


def motion_spec(scenes: list[dict], trans: list[dict], duration: float, det: dict) -> dict:
    lens = sorted(sc["duration"] for sc in scenes)
    q = statistics.quantiles(lens, n=4) if len(lens) >= 2 else [lens[0]] * 3
    quarters = []
    for k in range(4):
        a, b = duration * k / 4, duration * (k + 1) / 4
        n = sum(1 for t in trans if a <= t["start"] < b)
        quarters.append({"from": round(a, 2), "to": round(b, 2), "boundaries": n,
                         "perMinute": round(n / max(b - a, 1e-6) * 60, 1)})
    vocab: dict[str, int] = {}
    for t in trans:
        vocab[t["type"]] = vocab.get(t["type"], 0) + 1
    cams: dict[str, int] = {}
    for sc in scenes:
        key = sc["measured"]["camera"].split(" (")[0].split(":")[0]
        cams[key] = cams.get(key, 0) + 1
    gradual = [t["duration"] for t in trans if t["type"] != "cut"]
    starts = [sc["start"] for sc in scenes]
    beats = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
    return {
        "measured": True,
        "duration": duration,
        "sceneCount": len(scenes),
        "averageScene": round(statistics.fmean(lens), 3),
        "sceneDurations": {"min": lens[0], "p25": round(q[0], 3), "median": round(statistics.median(lens), 3),
                           "p75": round(q[2], 3), "max": lens[-1]},
        "boundariesPerMinute": round(len(trans) / max(duration, 1e-6) * 60, 1),
        "byQuarter": quarters,
        "beatIntervals": beats,
        "transitionVocabulary": vocab,
        "hardCutShare": round(vocab.get("cut", 0) / len(trans), 2) if trans else None,
        "gradualTransitionSeconds": round(statistics.fmean(gradual), 3) if gradual else None,
        "cameraVocabulary": cams,
        "motionEnergy": {"mean": round(statistics.fmean(sc["measured"]["motionEnergy"] for sc in scenes), 4),
                         "max": max(sc["measured"]["motionEnergy"] for sc in scenes)},
        "opening": det["opening"] or {"type": "starts on picture", "firstScene": lens and scenes[0]["duration"]},
        "closing": det["closing"] or {"type": "ends on picture", "lastScene": scenes[-1]["duration"]},
    }


def validate(bd: dict, root: Path) -> list[str]:
    """Structural checks; any message means the breakdown cannot be used."""
    errs = []
    dur = float((bd.get("metadata") or {}).get("duration") or 0)
    scenes = bd.get("scenes") or []
    if dur <= 0:
        errs.append("no duration")
    if not scenes:
        errs.append("no scenes")
        return errs
    ids = [s["id"] for s in scenes]
    if len(set(ids)) != len(ids):
        errs.append("duplicate scene ids")
    if abs(scenes[0]["start"]) > 0.05:
        errs.append("the first scene does not start at 0")
    if abs(scenes[-1]["end"] - dur) > 0.1:
        errs.append(f"the last scene ends at {scenes[-1]['end']}s, not at the video's end ({dur}s)")
    prev_end = 0.0
    for s in scenes:
        if s["end"] <= s["start"]:
            errs.append(f"{s['id']} ends before it starts")
        if s["start"] < prev_end - 1e-6:
            errs.append(f"{s['id']} overlaps the previous scene")
        prev_end = s["end"]
        if not s.get("frames"):
            errs.append(f"{s['id']} has no evidence frames")
    trans = bd.get("transitions") or []
    if len(trans) != len(scenes) - 1:
        errs.append("every pair of adjacent scenes needs exactly one transition")
    for k, t in enumerate(trans):
        if t.get("from") not in ids or t.get("to") not in ids:
            errs.append(f"{t.get('id')} references an unknown scene")
        elif ids.index(t["to"]) != ids.index(t["from"]) + 1:
            errs.append(f"{t.get('id')} does not join adjacent scenes")
        if k < len(scenes) - 1 and (abs(t["start"] - scenes[k]["end"]) > 1e-3 or abs(t["end"] - scenes[k + 1]["start"]) > 1e-3):
            errs.append(f"{t.get('id')} does not sit between {scenes[k]['id']} and {scenes[k + 1]['id']}")
    covered = sum(s["duration"] for s in scenes) + sum(t["end"] - t["start"] for t in trans)
    if abs(covered - dur) > 0.1:
        errs.append(f"scenes and transitions cover {covered:.2f}s of {dur:.2f}s")
    for f in _all_frames(bd):
        if not (root / f["file"]).is_file():
            errs.append(f"missing evidence file {f['file']}")
    return errs


def summary(bd: dict) -> str:
    m, ms = bd["metadata"], bd["motionSpec"]
    vocab = ", ".join(f"{k} ×{v}" for k, v in sorted(ms["transitionVocabulary"].items())) or "none"
    return (f"{fmt_time(m['duration'])} · {m['width']}×{m['height']} ({m['aspect']}) · {m['fps']} fps · "
            f"audio {'yes' if m['audio']['present'] else 'no'} · {ms['sceneCount']} scenes "
            f"(avg {ms['averageScene']} s) · transitions: {vocab}"
            + (" · cached" if bd.get("cached") else ""))
