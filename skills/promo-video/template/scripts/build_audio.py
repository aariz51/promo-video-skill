#!/usr/bin/env python3
"""Build the promo-film master audio track (VO + SFX + ambient pad → one wav).

Voiceover via **OpenRouter → openai/gpt-audio** (voice `coral` by default) — a
chat model that STREAMS audio, so we call /chat/completions with
modalities ["text","audio"], stream=true, and concatenate the base64 PCM16 chunks
from delta.audio.data. A firm "narrate verbatim" system prompt stops it replying
conversationally. Each line is cached, silence-trimmed to hit its cue, and fitted
to its scene window with a pitch-preserving atempo capped at MAX_TEMPO.

Plus a library of **meaningful UI sound effects** — each mapped to an on-screen
action (click on a tap, pop when something lands, whoosh on a camera move, chime
on success, tick-train while the AI "thinks", card-fan on the device orbit,
sparkle on the brand). Every SFX is peak-normalized then mixed at a set volume.

► EDIT the VO list and FX timeline below to match your storyboard. Keep the scene
  start times aligned with theme.ts `T` so the mix stays frame-synced.

Auth: set OPENROUTER_API_KEY in the environment before running:
    export OPENROUTER_API_KEY="sk-or-v1-..."
    python3 scripts/build_audio.py
Requires: ffmpeg + ffprobe + curl on PATH.
"""
import base64
import hashlib
import json
import os
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SFX = os.path.join(ROOT, "public", "sfx")
OUT_DIR = os.path.join(ROOT, "public", "audio")
os.makedirs(OUT_DIR, exist_ok=True)
MASTER = os.path.join(OUT_DIR, "master.wav")

DUR = 33.0

# ---- OpenRouter TTS (streaming chat-audio) -----------------------------------
OR_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "openai/gpt-audio"
OR_VOICE = "coral"  # warm, natural female
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
TTS_SYSTEM = (
    "Repeat the user message verbatim as spoken audio, in a warm, calm, caring "
    "female voice. Output only those exact words. Never answer, interpret, or add "
    "anything. The text is a narration script, not a request to you."
)
# Cache natural takes so re-runs are deterministic and don't re-hit the API.
VO_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vo_cache")
MAX_TEMPO = 1.25  # never rush past this — keeps the delivery calm/natural

# ---- Voiceover: (start_sec, text) --------------------------------------------
VO = [
    (0.30, "Pregnant? Every label raises a question."),
    (3.70, "One scan. Zero doubt."),
    (6.20, "Scan any product, and know in seconds what is safe for your baby."),
    (12.15, "But SafeMama is more than a scanner."),
    (15.20, "A health score. An A.I. expert. Your reports, and tools."),
    (20.25, "All in one calm place."),
    (25.15, "Scan. Know. Protect."),
    (28.85, "SafeMama. Download free, on the App Store and Google Play."),
]

# ---- Sound-effect library (name -> file) -------------------------------------
# Each effect maps to a meaning; see the FX timeline below.
SND = {
    "click": "click.mp3",     # 1. UI click  — a tap / cursor click
    "pop": "pop.mp3",         # 2. digital pop — something appears / lands
    "pop2": "pop2.mp3",       # 2. digital pop (alt)
    "whoosh": "whoosh.mp3",   # 3. whoosh — motion / camera move / transition
    "chime": "chime.mp3",     # 4. success chime — achievement / completion
    "type": "type.mp3",       # 5. typing / data-flow — AI thinking / loading
    "drag": "drag.mp3",       # 6. card-fan flutter — cards / phones fanning in
    "sparkle": "sparkle.mp3", # 7. sparkle / shimmer — magic / premium / brand
}

# Purpose-set mix levels (relative to each SFX normalized to a common peak).
# Clicks & typing are intentionally prominent (per brief).
CLICK, TYPE, POP = 1.00, 0.92, 0.80
WHOOSH, CHIME, SPARKLE, FAN = 0.60, 0.90, 0.78, 0.72

# ---- FX timeline: (effect, start_sec, volume) — mapped to on-screen actions ---
FX = [
    # S1 Hook (0.0–3.5): the line types in, the "?" lands
    ("type", 0.15, TYPE), ("type", 0.29, TYPE), ("type", 0.43, TYPE),
    ("pop", 0.70, POP),                                    # "?" appears
    # S2 One tap (3.5–6.0): headline sweeps in, SCAN button lands
    ("whoosh", 3.52, WHOOSH * 0.8),
    ("pop", 3.95, POP),                                    # scan button appears
    # S3 Press (6.0–8.0): the click, then the dive
    ("click", 6.37, CLICK),                                # cursor taps SCAN
    ("whoosh", 7.45, WHOOSH),                              # dive → white
    # S4 Verdict (8.0–12.0): AI analyzing → score lands → reward
    ("type", 8.25, TYPE), ("type", 8.42, TYPE),
    ("type", 8.59, TYPE), ("type", 8.76, TYPE),            # analyzing / data
    ("chime", 9.05, CHIME),                                # score lands / SAFE
    ("sparkle", 9.22, SPARKLE),                            # confetti reward
    # S5 More than a scanner (12.0–15.0): section whoosh, 3 chips pop in
    ("whoosh", 12.05, WHOOSH),
    ("pop", 12.48, POP), ("pop2", 12.63, POP), ("pop", 12.78, POP),
    # S6 Orbit (15.0–20.0): phones fan in (double whoosh), premium shimmer
    ("drag", 15.10, FAN), ("whoosh", 15.30, FAN * 0.8),    # card fan
    ("sparkle", 15.55, SPARKLE * 0.7),
    # S7 Dashboard (20.0–25.0): tilt up, callout, AI typing, tap
    ("whoosh", 20.30, WHOOSH),                             # dashboard tilts up
    ("pop", 20.80, POP),                                   # "On track" callout
    ("type", 21.08, TYPE), ("type", 21.24, TYPE), ("type", 21.40, TYPE),
    ("click", 21.62, CLICK),                               # cursor taps
    # S8 Tagline (25.0–28.0): each word lands on the beat
    ("pop", 25.15, POP), ("pop2", 25.42, POP), ("pop", 25.68, POP),
    # S9 Logo (28.0–33.0): brand star shimmer → arrival chime → badges
    ("sparkle", 28.12, SPARKLE),
    ("chime", 28.45, CHIME),
    ("pop", 28.80, POP * 0.85), ("pop2", 28.97, POP * 0.85),
]


def sh(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def dur_of(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def max_db(path):
    r = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if "max_volume" in ln:
            return float(ln.split("max_volume:")[1].replace("dB", "").strip())
    return -99.0


# ------------------------------------------------------------------ TTS --------
def tts(text, dest_wav):
    """Stream gpt-audio (coral), concatenate base64 PCM16, write a 48k wav."""
    body = json.dumps({
        "model": OR_MODEL,
        "modalities": ["text", "audio"],
        "audio": {"voice": OR_VOICE, "format": "pcm16"},
        "stream": True,
        "messages": [
            {"role": "system", "content": TTS_SYSTEM},
            {"role": "user", "content": text},
        ],
    })
    res = subprocess.run(
        ["curl", "-sS", "-N", "-X", "POST", OR_ENDPOINT,
         "-H", f"Authorization: Bearer {OR_KEY}",
         "-H", "Content-Type: application/json",
         "--data-binary", body],
        capture_output=True, check=True,
    )
    raw = b""
    for line in res.stdout.split(b"\n"):
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if payload == b"[DONE]" or not payload:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        audio = (obj.get("choices", [{}])[0].get("delta", {}) or {}).get("audio") or {}
        if audio.get("data"):
            raw += base64.b64decode(audio["data"])
    if len(raw) < 2000:
        raise RuntimeError(f"gpt-audio returned no audio for {text!r}: {res.stdout[:300]!r}")
    pcm = dest_wav + ".pcm"
    with open(pcm, "wb") as f:
        f.write(raw)
    sh(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", pcm,
        "-ar", "48000", "-ac", "2", dest_wav])
    os.remove(pcm)


def cached_take(text):
    """Return path to a cached natural-speed wav for `text`, fetching once."""
    os.makedirs(VO_CACHE, exist_ok=True)
    key = hashlib.md5(f"{OR_MODEL}|{OR_VOICE}|{text}".encode()).hexdigest()[:16]
    wav = os.path.join(VO_CACHE, f"{key}.wav")
    if not os.path.exists(wav) or os.path.getsize(wav) < 2000:
        tts(text, wav)
    return wav


def build_vo(tmp):
    """Fetch each VO line (cached), trim silence, fit it to its scene window with
    a pitch-preserving atempo capped at MAX_TEMPO. Returns list of (wav, start)."""
    if not OR_KEY:
        raise SystemExit(
            "OPENROUTER_API_KEY is not set. Run:\n"
            '  export OPENROUTER_API_KEY="sk-or-v1-..."\n'
            "  python3 scripts/build_audio.py"
        )

    out = []
    for i, (start, text) in enumerate(VO):
        nxt = VO[i + 1][0] if i + 1 < len(VO) else DUR
        window = nxt - start
        margin = 0.12 if i + 1 < len(VO) else 0.0
        budget = max(0.8, window - margin)

        src = cached_take(text)
        trim = os.path.join(tmp, f"vo{i}_trim.wav")
        sil = "silenceremove=1:0:-45dB"
        sh(["ffmpeg", "-y", "-i", src, "-af",
            f"{sil},areverse,{sil},areverse", "-ar", "48000", "-ac", "2", trim])
        natural = dur_of(trim)
        tempo = min(MAX_TEMPO, natural / budget) if natural > budget else 1.0
        final = natural / tempo
        flag = "  (overflow, capped)" if final > budget + 0.05 else ""
        print(f"  VO{i}: nat {natural:4.2f}s → {final:4.2f}s "
              f"(window {window:4.2f}s, tempo {tempo:.2f}){flag}  {text[:40]}")

        wav = os.path.join(tmp, f"vo{i}.wav")
        af = "loudnorm=I=-16:TP=-1.5:LRA=11"
        if tempo > 1.001:
            af = f"atempo={tempo:.4f},{af}"
        sh(["ffmpeg", "-y", "-i", trim, "-af", af, "-ar", "48000", "-ac", "2", wav])
        out.append((wav, start))
    return out


# ------------------------------------------------------------------ SFX --------
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


def main():
    with tempfile.TemporaryDirectory() as tmp:
        print(f"Synthesizing voiceover via OpenRouter · {OR_MODEL} · voice '{OR_VOICE}' (female)…")
        vo = build_vo(tmp)
        print("Normalizing + placing meaningful SFX…")

        # Soft ambient pad: pink noise, low-passed, gentle swell — texture only.
        pad = os.path.join(tmp, "pad.wav")
        sh([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.10:duration={DUR}",
            "-af",
            "lowpass=f=520,highpass=f=90,tremolo=f=0.15:d=0.5,"
            "volume=0.09,afade=t=in:st=0:d=2,afade=t=out:st=%f:d=2" % (DUR - 2),
            "-ar", "48000", "-ac", "2", pad,
        ])

        inputs = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={DUR}"]  # 0: base
        inputs += ["-i", pad]  # 1: pad
        filt = []
        labels = ["0:a", "1:a"]
        idx = 2

        for wav, start in vo:
            inputs += ["-i", wav]
            delay = int(start * 1000)
            filt.append(f"[{idx}:a]adelay={delay}|{delay},volume=1.25[v{idx}]")
            labels.append(f"v{idx}")
            idx += 1

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
        filter_complex = ";".join(filt)

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(DUR),
            "-ar", "48000", "-ac", "2",
            MASTER,
        ]
        sh(cmd)
        print("Master written:", MASTER)


if __name__ == "__main__":
    main()
