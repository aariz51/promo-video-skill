#!/usr/bin/env python3
"""Build the promo-film master audio track (SFX + ambient pad -> one wav).

**No API key. No network. No account.** Everything here runs locally with ffmpeg
against the sound effects bundled in `public/sfx/`. If you have Claude Code or
Codex, you already have everything this needs.

The design principle is that every effect must *mean* something at the instant it
fires: a click on a tap, a pop when something lands, a whoosh on a camera move, a
chime on the reward, a tick-train while the product "thinks". Sound that maps to
on-screen action is what separates a premium film from a slideshow with noise on
top. Effects are peak-normalized to a common level, then mixed at per-purpose
volumes over a soft non-melodic pad, and the master is limited to about -1 dB.

► EDIT the FX timeline below to match your storyboard. Keep the cue times aligned
  with `T` in src/theme.ts so the mix stays frame-synced across every orientation.

    python3 scripts/build_audio.py              # writes public/audio/master.wav
    python3 scripts/build_audio.py --duration 40

Then set AUDIO_SRC = "audio/master.wav" in src/theme.ts.

Requires: ffmpeg + ffprobe on PATH. That is the whole dependency list.

Adding narration is deliberately out of scope: it would mean either an API key or
a platform-specific TTS binary, and the core workflow must not require either.
See docs/voiceover.md if you want to add a voice track yourself.
"""
import argparse
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX = os.path.join(ROOT, "public", "sfx")
OUT_DIR = os.path.join(ROOT, "public", "audio")
MASTER = os.path.join(OUT_DIR, "master.wav")

# Seconds. MUST equal theme.ts DURATION / FPS (1980 / 60 = 33.0).
DUR = 33.0

# ---- Sound-effect library (name -> file) -------------------------------------
# Each effect maps to a meaning; see the FX timeline below.
SND = {
    "click": "click.mp3",     # a tap / cursor click
    "pop": "pop.mp3",         # something appears / lands
    "pop2": "pop2.mp3",       # digital pop (alt)
    "whoosh": "whoosh.mp3",   # motion / camera move / transition
    "chime": "chime.mp3",     # success / completion
    "type": "type.mp3",       # typing / data-flow — the product "thinking"
    "drag": "drag.mp3",       # card-fan flutter
    "sparkle": "sparkle.mp3", # shimmer — magic / premium / brand
}

# Purpose-set mix levels (relative to each SFX normalized to a common peak).
# Clicks and typing are intentionally prominent so interactions read clearly.
CLICK, TYPE, POP = 1.00, 0.92, 0.80
WHOOSH, CHIME, SPARKLE, FAN = 0.60, 0.90, 0.78, 0.72

# ---- FX timeline: (effect, start_sec, volume) — mapped to on-screen actions ---
FX = [
    # S1 Hook (0.0–3.5): the line types in, the "?" lands
    ("type", 0.15, TYPE), ("type", 0.29, TYPE), ("type", 0.43, TYPE),
    ("pop", 0.70, POP),                                    # "?" appears
    # S2 One tap (3.5–6.0): headline sweeps in, the button lands
    ("whoosh", 3.52, WHOOSH * 0.8),
    ("pop", 3.95, POP),
    # S3 Press (6.0–8.0): the click, then the dive
    ("click", 6.37, CLICK),
    ("whoosh", 7.45, WHOOSH),                              # dive → bloom
    # S4 Verdict (8.0–12.0): thinking → result lands → reward
    ("type", 8.25, TYPE), ("type", 8.42, TYPE),
    ("type", 8.59, TYPE), ("type", 8.76, TYPE),
    ("chime", 9.05, CHIME),                                # result lands
    ("sparkle", 9.22, SPARKLE),                            # confetti reward
    # S5 More than (12.0–15.0): section whoosh, 3 chips pop in
    ("whoosh", 12.05, WHOOSH),
    ("pop", 12.48, POP), ("pop2", 12.63, POP), ("pop", 12.78, POP),
    # S6 Orbit (15.0–20.0): screens fan in, premium shimmer
    ("drag", 15.10, FAN), ("whoosh", 15.30, FAN * 0.8),
    ("sparkle", 15.55, SPARKLE * 0.7),
    # S7 Dashboard (20.0–25.0): tilt up, callout, thinking, tap
    ("whoosh", 20.30, WHOOSH),
    ("pop", 20.80, POP),                                   # callout
    ("type", 21.08, TYPE), ("type", 21.24, TYPE), ("type", 21.40, TYPE),
    ("click", 21.62, CLICK),
    # S8 Tagline (25.0–28.0): each word lands on the beat
    ("pop", 25.15, POP), ("pop2", 25.42, POP), ("pop", 25.68, POP),
    # S9 Logo (28.0–33.0): shimmer → arrival chime → badges
    ("sparkle", 28.12, SPARKLE),
    ("chime", 28.45, CHIME),
    ("pop", 28.80, POP * 0.85), ("pop2", 28.97, POP * 0.85),
]


def sh(cmd):
    """Run a command quietly, but report what actually failed if it does."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        tail = (res.stderr or "").strip().splitlines()[-6:]
        raise SystemExit(
            f"Command failed ({cmd[0]}, exit {res.returncode}):\n  "
            + " ".join(cmd[:6])
            + "\n" + "\n".join("  " + ln for ln in tail)
        )


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
    if os.path.exists(dst):
        return dst
    gain = target - max_db(src)
    sh(["ffmpeg", "-y", "-i", src, "-af", f"volume={gain:.2f}dB",
        "-ar", "48000", "-ac", "2", dst])
    return dst


def preflight():
    """Fail early and legibly when something required is missing."""
    missing = [b for b in ("ffmpeg", "ffprobe") if shutil.which(b) is None]
    if missing:
        raise SystemExit(
            "Missing required tool(s) on PATH: " + ", ".join(missing) + "\n"
            "  macOS:  brew install ffmpeg\n"
            "  Debian: sudo apt install ffmpeg"
        )
    for name in sorted({n for n, _, _ in FX}):
        if name not in SND:
            raise SystemExit(
                f"FX timeline references unknown effect '{name}'.\n"
                f"Known effects: {', '.join(sorted(SND))}"
            )
        path = os.path.join(SFX, SND[name])
        if not os.path.exists(path):
            raise SystemExit(
                f"Sound effect '{name}' is missing: {path}\n"
                "Restore public/sfx/, or remove that effect from the FX timeline."
            )


def main():
    ap = argparse.ArgumentParser(description="Build the film's SFX + pad master.")
    ap.add_argument("--duration", type=float, default=DUR,
                    help=f"Master length in seconds (default {DUR}; keep equal to "
                         "theme.ts DURATION / FPS).")
    ap.add_argument("--no-pad", action="store_true",
                    help="Skip the ambient pad and mix sound effects only.")
    args = ap.parse_args()
    dur = args.duration

    preflight()
    os.makedirs(OUT_DIR, exist_ok=True)

    late = [(n, t) for n, t, _ in FX if t >= dur]
    if late:
        print(f"  note: {len(late)} cue(s) fall at or past {dur:.1f}s and will be "
              f"inaudible (first: '{late[0][0]}' at {late[0][1]:.2f}s)")

    with tempfile.TemporaryDirectory() as tmp:
        print(f"Mixing {len(FX)} mapped sound effects over {dur:.1f}s…")

        inputs = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur}"]  # 0: base
        labels = ["0:a"]
        filt = []
        idx = 1

        if not args.no_pad:
            # Soft ambient pad: pink noise, low-passed, gentle swell — texture only,
            # deliberately non-melodic so it never fights the picture.
            pad = os.path.join(tmp, "pad.wav")
            sh([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.10:duration={dur}",
                "-af",
                "lowpass=f=520,highpass=f=90,tremolo=f=0.15:d=0.5,"
                f"volume=0.09,afade=t=in:st=0:d=2,afade=t=out:st={dur - 2}:d=2",
                "-ar", "48000", "-ac", "2", pad,
            ])
            inputs += ["-i", pad]
            labels.append("1:a")
            idx = 2

        for name, start, vol in FX:
            src = norm_sfx(tmp, name)
            inputs += ["-i", src]
            delay = int(start * 1000)
            filt.append(f"[{idx}:a]adelay={delay}|{delay},volume={vol:.3f}[v{idx}]")
            labels.append(f"v{idx}")
            idx += 1

        mix = "".join(f"[{l}]" for l in labels)
        filt.append(
            f"{mix}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
            f"alimiter=limit=0.89:level=disabled[out]"
        )

        sh(["ffmpeg", "-y"] + inputs + [
            "-filter_complex", ";".join(filt),
            "-map", "[out]",
            "-t", str(dur),
            "-ar", "48000", "-ac", "2",
            MASTER,
        ])

    print("Master written:", MASTER)
    print('Now set AUDIO_SRC = "audio/master.wav" in src/theme.ts.')


if __name__ == "__main__":
    main()
