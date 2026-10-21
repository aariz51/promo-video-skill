"""The sound-effect library, synthesised. Original work, MIT, no third-party samples.

The effects bundled before v5 had no verified provenance. Every effect here is generated
by ffmpeg's `aevalsrc` from a formula, so its licence is this repository's and the same
version always produces the same bytes (aevalsrc's `random()` is a seeded sequence).
Effects are short and non-melodic by construction: single impacts, filtered noise,
pitch glides and at most one sustained partial set (the chime), never a phrase.

`build_library(dest)` writes `<name>.wav` (48 kHz stereo) for every effect and returns the
paths. Generation takes about a second; results are cached by recipe version.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .util import PromoError, require_tools, run

VERSION = 1
RATE = 48000

# name → (seconds, aevalsrc expression in t, post filter chain or "")
# exp(-k*t) envelopes; chirps use phase = 2π(f0·t + (f1-f0)·t²/(2d)).
RECIPES: dict[str, tuple[float, str, str]] = {
    "click": (0.035, "(random(0)*2-1)*exp(-t*260)*0.9+sin(2*PI*2900*t)*exp(-t*420)*0.35",
              "highpass=f=1200"),
    "tick": (0.07, "sin(2*PI*2200*t)*exp(-t*160)*0.8", ""),
    "tick2": (0.045, "sin(2*PI*3300*t)*exp(-t*240)*0.7", ""),
    "type": (0.04, "(random(0)*2-1)*exp(-t*220)*0.6+sin(2*PI*190*t)*exp(-t*120)*0.5",
             "bandpass=f=2400:width_type=o:w=2.5"),
    "pop": (0.12, "sin(2*PI*(620*t-2600*t*t))*exp(-t*38)*0.9", ""),
    "pop2": (0.07, "sin(2*PI*(1150*t-4200*t*t))*exp(-t*60)*0.8", ""),
    "whoosh": (0.55, "(random(0)*2-1)*pow(sin(PI*t/0.55),3)*0.9",
               "highpass=f=350,lowpass=f=3200"),
    "drag": (0.28, "(random(0)*2-1)*pow(sin(PI*t/0.28),2)*0.7", "lowpass=f=1400,highpass=f=120"),
    "chime": (0.9, "(sin(2*PI*1318.5*t)+0.4*sin(2*PI*2637*t)+0.15*sin(2*PI*3955.5*t))*exp(-t*5.5)*0.5"
                   "*(1-exp(-t*900))", ""),
    "sparkle": (0.7, "(sin(2*PI*4186*t)*exp(-t*14)+0.8*sin(2*PI*5274*t)*exp(-(t-0.09)*16)*gte(t,0.09)"
                     "+0.6*sin(2*PI*6272*t)*exp(-(t-0.19)*18)*gte(t,0.19))*0.35", ""),
    "riser": (0.7, "((random(0)*2-1)*0.5+0.5*sin(2*PI*(180*t+430*t*t)))*pow(t/0.7,2)*(1-exp(-(0.7-t)*90))",
              "highpass=f=200,lowpass=f=5000"),
    "rise": (0.4, "sin(2*PI*(300*t+375*t*t))*sin(PI*t/0.4)*0.6", ""),
    "thud": (0.34, "(sin(2*PI*(72*t-38*t*t))*exp(-t*13)+(random(0)*2-1)*exp(-t*90)*0.3)*0.95",
             "lowpass=f=900"),
    "kick": (0.31, "sin(2*PI*(110*t-95*t*t))*exp(-t*16)*0.95", ""),
    "dive": (0.7, "sin(2*PI*(900*t-536*t*t))*exp(-t*3.5)*0.6", ""),
    "ascent": (2.1, "sin(2*PI*(220*t+157*t*t))*sin(PI*t/2.1)*0.45+(random(0)*2-1)*sin(PI*t/2.1)*0.06",
               "lowpass=f=4000"),
    "braam": (0.8, "(sin(2*PI*55*t)+0.5*sin(2*PI*110*t)+0.3*sin(2*PI*165*t)+0.2*sin(2*PI*220*t))*exp(-t*3)"
                   "*(1-exp(-t*60))*0.45", "lowpass=f=1800"),
}


def recipe_hash() -> str:
    return hashlib.sha1(json.dumps([VERSION, RATE, RECIPES], sort_keys=True).encode()).hexdigest()[:12]


def build_library(dest: str | Path) -> dict[str, Path]:
    """Synthesise every effect into `dest` (cached by recipe hash). Returns name → path."""
    require_tools("ffmpeg")
    root = Path(dest) / f"synth-{recipe_hash()}"
    root.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, (secs, expr, post) in RECIPES.items():
        path = root / f"{name}.wav"
        if not path.is_file() or path.stat().st_size == 0:
            # Fade the last 5 ms so no effect ends on a click; fixed metadata keeps bytes stable.
            chain = ",".join(x for x in (post, f"afade=t=out:st={max(0.0, secs - 0.005):.3f}:d=0.005") if x)
            tmp = path.with_suffix(".tmp.wav")
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                 f"aevalsrc='{expr}':s={RATE}:d={secs}:c=mono", "-af", chain, "-ac", "2", "-ar", str(RATE),
                 "-c:a", "pcm_s16le", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact",
                 str(tmp)])
            if not tmp.is_file() or tmp.stat().st_size < 100:
                raise PromoError(f"could not synthesise sound effect '{name}'")
            tmp.replace(path)
        out[name] = path
    return out
