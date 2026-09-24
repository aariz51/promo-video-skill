#!/usr/bin/env python3
"""Build the film's audio master: mapped sound effects (+ optional voiceover) -> one wav.

**No API key. No network. No account.** This runs locally with ffmpeg against the
sound effects bundled in `public/sfx/`.

Every effect must *mean* something at the instant it fires: a click on a tap, a pop
when something lands, a whoosh on a camera move, a chime when a result resolves, a
typing tick-train while text writes itself. Sound mapped to on-screen action is what
separates a finished film from a slideshow with noise on top. There is no music and no
ambient bed by default.

    python3 scripts/build_audio.py                  # uses ./sound.json if present
    python3 scripts/build_audio.py --duration 30
    python3 scripts/build_audio.py --pad            # opt in to a soft noise bed

If `public/audio/vo/manifest.json` exists (see scripts/voiceover.py, which is
optional), the voice lines are placed at their cue times and the effects are
side-chain ducked underneath them so speech always reads.

sound.json (optional; overrides the built-in example timeline):

    { "duration": 33, "cues": [ {"fx": "click", "at": 6.37, "vol": 1.0}, ... ] }

Then set AUDIO_SRC = "audio/master.wav" in src/theme.ts.
Requires: ffmpeg + ffprobe on PATH.
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX = os.path.join(ROOT, "public", "sfx")
OUT_DIR = os.path.join(ROOT, "public", "audio")
MASTER = os.path.join(OUT_DIR, "master.wav")
VO_DIR = os.path.join(OUT_DIR, "vo")

# Seconds. MUST equal theme.ts DURATION / FPS (1980 / 60 = 33.0).
DUR = 33.0

# ---- Sound-effect library (name -> file) -------------------------------------
SND = {
    "click": "click.mp3",     # a tap / cursor click
    "pop": "pop.mp3",         # something appears / lands
    "pop2": "pop2.mp3",       # digital pop (alt)
    "whoosh": "whoosh.mp3",   # motion / camera move / transition
    "chime": "chime.mp3",     # success / completion / result resolves
    "type": "type.mp3",       # typing / text writing itself
    "drag": "drag.mp3",       # card-fan flutter
    "sparkle": "sparkle.mp3", # shimmer — reveal / brand
}

CLICK, TYPE, POP = 1.00, 0.92, 0.80
WHOOSH, CHIME, SPARKLE, FAN = 0.60, 0.90, 0.78, 0.72

# ---- Built-in example timeline (matches the template's nine scenes) ----------
FX = [
    ("type", 0.15, TYPE), ("type", 0.29, TYPE), ("type", 0.43, TYPE),
    ("pop", 0.70, POP),
    ("whoosh", 3.52, WHOOSH * 0.8), ("pop", 3.95, POP),
    ("click", 6.37, CLICK), ("whoosh", 7.45, WHOOSH),
    ("type", 8.25, TYPE), ("type", 8.42, TYPE), ("type", 8.59, TYPE), ("type", 8.76, TYPE),
    ("chime", 9.05, CHIME), ("sparkle", 9.22, SPARKLE),
    ("whoosh", 12.05, WHOOSH),
    ("pop", 12.48, POP), ("pop2", 12.63, POP), ("pop", 12.78, POP),
    ("drag", 15.10, FAN), ("whoosh", 15.30, FAN * 0.8), ("sparkle", 15.55, SPARKLE * 0.7),
    ("whoosh", 20.30, WHOOSH), ("pop", 20.80, POP),
    ("type", 21.08, TYPE), ("type", 21.24, TYPE), ("type", 21.40, TYPE),
    ("click", 21.62, CLICK),
    ("pop", 25.15, POP), ("pop2", 25.42, POP), ("pop", 25.68, POP),
    ("sparkle", 28.12, SPARKLE), ("chime", 28.45, CHIME),
    ("pop", 28.80, POP * 0.85), ("pop2", 28.97, POP * 0.85),
]


def sh(cmd):
    """Run a command quietly, but report what actually failed if it does."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tail = (res.stderr or "").strip().splitlines()[-6:]
        raise SystemExit(f"Command failed ({cmd[0]}, exit {res.returncode}):\n  "
                         + " ".join(cmd[:6]) + "\n" + "\n".join("  " + ln for ln in tail))


def max_db(path):
    r = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if "max_volume" in ln:
            return float(ln.split("max_volume:")[1].replace("dB", "").strip())
    return -99.0


def norm_sfx(tmp, name, target=-3.0):
    """Peak-normalize one SFX file to `target` dBFS, 48k stereo (cached per run)."""
    src = os.path.join(SFX, SND[name])
    dst = os.path.join(tmp, f"sfx_{name}.wav")
    if not os.path.exists(dst):
        gain = target - max_db(src)
        sh(["ffmpeg", "-y", "-i", src, "-af", f"volume={gain:.2f}dB", "-ar", "48000", "-ac", "2", dst])
    return dst


def load_timeline(path):
    if path and os.path.exists(path):
        spec = json.load(open(path))
        cues = [(c["fx"], float(c["at"]), float(c.get("vol", 0.8))) for c in spec.get("cues", [])]
        return cues, spec.get("duration")
    return FX, None


def load_vo():
    manifest = os.path.join(VO_DIR, "manifest.json")
    if not os.path.exists(manifest):
        return []
    lines = json.load(open(manifest)).get("lines", [])
    out = []
    for ln in lines:
        path = os.path.join(VO_DIR, ln["file"])
        if not os.path.exists(path):
            raise SystemExit(f"Voiceover manifest lists {ln['file']} but it is missing. Re-run voiceover.py.")
        out.append((path, float(ln["at"])))
    return out


def preflight(cues):
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise SystemExit("Missing required tool(s) on PATH: " + ", ".join(missing) + "\n"
                         "  macOS:  brew install ffmpeg\n  Debian: sudo apt install ffmpeg")
    for name in sorted({n for n, _, _ in cues}):
        if name not in SND:
            raise SystemExit(f"Timeline references unknown effect '{name}'.\n"
                             f"Known effects: {', '.join(sorted(SND))}")
        path = os.path.join(SFX, SND[name])
        if not os.path.exists(path):
            raise SystemExit(f"Sound effect '{name}' is missing: {path}\n"
                             "Restore public/sfx/, or remove that effect from the timeline.")


def main():
    ap = argparse.ArgumentParser(description="Build the film's audio master.")
    ap.add_argument("--duration", type=float, default=None,
                    help=f"seconds (default: sound.json 'duration', else {DUR})")
    ap.add_argument("--timeline", default=os.path.join(ROOT, "sound.json"),
                    help="cue file (default ./sound.json; falls back to the built-in example)")
    ap.add_argument("--pad", action="store_true", help="add a soft non-melodic noise bed (off by default)")
    ap.add_argument("--no-vo", action="store_true", help="ignore public/audio/vo even if present")
    args = ap.parse_args()

    cues, spec_dur = load_timeline(args.timeline)
    dur = args.duration or spec_dur or DUR
    preflight(cues)
    vo = [] if args.no_vo else load_vo()
    os.makedirs(OUT_DIR, exist_ok=True)

    late = [(n, t) for n, t, _ in cues if t >= dur]
    if late:
        print(f"  note: {len(late)} cue(s) fall at or past {dur:.1f}s and will be inaudible "
              f"(first: '{late[0][0]}' at {late[0][1]:.2f}s)")

    with tempfile.TemporaryDirectory() as tmp:
        print(f"Mixing {len(cues)} sound effects" + (f" + {len(vo)} voice lines" if vo else "")
              + f" over {dur:.1f}s" + (" (with pad)" if args.pad else " (no music, no bed)") + "…")
        inputs = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur}"]
        filt, fx_labels, vo_labels, idx = [], ["0:a"], [], 1

        if args.pad:
            pad = os.path.join(tmp, "pad.wav")
            sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.10:duration={dur}",
                "-af", "lowpass=f=520,highpass=f=90,tremolo=f=0.15:d=0.5,"
                f"volume=0.09,afade=t=in:st=0:d=2,afade=t=out:st={dur - 2}:d=2",
                "-ar", "48000", "-ac", "2", pad])
            inputs += ["-i", pad]
            fx_labels.append(f"{idx}:a")
            idx += 1

        for name, start, vol in cues:
            inputs += ["-i", norm_sfx(tmp, name)]
            d = int(start * 1000)
            filt.append(f"[{idx}:a]adelay={d}|{d},volume={vol:.3f}[f{idx}]")
            fx_labels.append(f"f{idx}")
            idx += 1

        for path, start in vo:
            inputs += ["-i", path]
            d = int(start * 1000)
            filt.append(f"[{idx}:a]adelay={d}|{d}[v{idx}]")
            vo_labels.append(f"v{idx}")
            idx += 1

        fx_mix = "".join(f"[{l}]" for l in fx_labels)
        filt.append(f"{fx_mix}amix=inputs={len(fx_labels)}:normalize=0:dropout_transition=0[fx]")
        if vo_labels:
            vo_mix = "".join(f"[{l}]" for l in vo_labels)
            filt.append(f"{vo_mix}amix=inputs={len(vo_labels)}:normalize=0:dropout_transition=0,"
                        f"apad=whole_dur={dur}[vo]")
            filt.append("[vo]asplit=2[vo_key][vo_out]")
            # Duck effects under speech: fast attack, gentle release, so a click still
            # reads between words but never masks a syllable.
            filt.append("[fx][vo_key]sidechaincompress=threshold=0.02:ratio=5:attack=8:release=260[fxd]")
            filt.append("[fxd]volume=0.85[fxd2]")
            filt.append("[fxd2][vo_out]amix=inputs=2:normalize=0:dropout_transition=0,"
                        "alimiter=limit=0.89:level=disabled[out]")
        else:
            filt.append("[fx]alimiter=limit=0.89:level=disabled[out]")

        sh(["ffmpeg", "-y"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[out]",
                                        "-t", str(dur), "-ar", "48000", "-ac", "2", MASTER])

    print("Master written:", MASTER)
    print('Now set AUDIO_SRC = "audio/master.wav" in src/theme.ts.')


if __name__ == "__main__":
    main()
