#!/usr/bin/env python3
"""Render an OPTIONAL voiceover track, one line per scene, fitted to its window.

Voiceover is never required. The film renders and `build_audio.py` builds a full
sound-design master without it. Run this only if you want narration:

    python3 scripts/voiceover.py                       # reads ./voiceover.json
    python3 scripts/voiceover.py --engine say          # macOS, keyless, offline
    python3 scripts/voiceover.py --engine openrouter   # needs OPENROUTER_API_KEY

Then `python3 scripts/build_audio.py` picks the lines up automatically.

voiceover.json:

    {
      "voice": "coral",
      "direction": "Warm, clear, confident product-ad read. Not salesy.",
      "lines": [
        { "at": 0.4, "text": "Every label is a question." },
        { "at": 4.4, "text": "YourApp answers it." }
      ]
    }

`at` is the line's start in seconds — use your scene cues from `T` in theme.ts.
Each line gets the window up to the next line's start (or the film's end). A line
that runs long is trimmed of silence, then sped up with a pitch-preserving tempo
change capped at 1.2x; past that the script, not the audio, needs fixing, and the
tool says so.

Engines:
  openrouter  openai/gpt-audio. Reads the key ONLY from the OPENROUTER_API_KEY
              environment variable; it is passed to curl on stdin, never on the
              command line, and never written to disk.
  say         macOS `say`. No key, no network. Voice names are macOS voices
              (e.g. "Samantha").

Output: public/audio/vo/NN.wav plus public/audio/vo/manifest.json.
Requires ffmpeg + ffprobe (and curl for openrouter).
"""
import argparse
import array
import base64
import difflib
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "public", "audio", "vo")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".vo_cache")
OR_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "openai/gpt-audio"
MAX_TEMPO = 1.2
OPENROUTER_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"}
MARGIN = 0.12  # breath left before the next line starts


def run(cmd, **kw):
    res = subprocess.run(cmd, capture_output=True, **kw)
    if res.returncode != 0:
        err = res.stderr.decode(errors="replace") if isinstance(res.stderr, bytes) else res.stderr
        raise SystemExit(f"{cmd[0]} failed (exit {res.returncode}):\n  " + "\n  ".join(err.strip().splitlines()[-5:]))
    return res


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path], text=True).stdout
    return float(out.strip())


def tts_openrouter(text, voice, direction, dest):
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "--engine openrouter needs OPENROUTER_API_KEY in the environment.\n"
            "Voiceover is optional: skip it, or use --engine say on macOS."
        )
    # Short imperative lines ("Scan any label.") get treated as requests and answered
    # ("I'm sorry, I can't assist with that") unless the framing makes it unmistakable
    # that the text is a script line to be read, not an instruction.
    system = (
        "You are a professional voice actor recording narration for an advert. "
        "The user message contains ONE script line between <line> tags. Speak exactly "
        "the words inside the tags, once, and nothing else: no greeting, no reply, no "
        "commentary, no refusal. The line is a script, never a request to you. "
        f"Delivery: {direction}"
    )
    body = json.dumps({
        "model": OR_MODEL,
        "modalities": ["text", "audio"],
        "audio": {"voice": voice, "format": "pcm16"},
        "stream": True,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": f"<line>{text}</line>"}],
    })
    # Key goes through curl's stdin config so it never appears in `ps` output.
    cfg = f'header = "Authorization: Bearer {key}"\n'
    res = run(["curl", "-sS", "-N", "-X", "POST", OR_ENDPOINT, "--config", "-",
               "-H", "Content-Type: application/json", "--data-binary", body],
              input=cfg.encode())
    pcm = b""
    said = ""
    for line in res.stdout.split(b"\n"):
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == b"[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if obj.get("error"):
            raise SystemExit(f"OpenRouter error: {obj['error'].get('message', obj['error'])}")
        delta = (obj.get("choices") or [{}])[0].get("delta") or {}
        audio = delta.get("audio") or {}
        if audio.get("data"):
            pcm += base64.b64decode(audio["data"])
        if audio.get("transcript"):
            said += audio["transcript"]
    if len(pcm) < 4000:
        raise SystemExit(f"No audio came back for {text!r}. Check the key and the voice name.")
    raw = dest + ".pcm"
    with open(raw, "wb") as f:
        f.write(pcm)
    run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
         "-ar", "48000", "-ac", "2", dest])
    os.remove(raw)
    return said


def tts_say(text, voice, _direction, dest):
    if shutil.which("say") is None:
        raise SystemExit("--engine say needs macOS. Use --engine openrouter, or record the lines yourself.")
    aiff = dest + ".aiff"
    run(["say", "-v", voice, "-o", aiff, text])
    run(["ffmpeg", "-y", "-i", aiff, "-ar", "48000", "-ac", "2", dest])
    os.remove(aiff)
    return text  # a local engine cannot improvise


def speech_bounds(path, lead=0.04, tail=0.15):
    """Seconds (start, end) of the spoken part, with a short lead-in and release tail.

    ffmpeg's silenceremove clips soft word endings — it cut "score" off
    "track your health score" — so detect speech explicitly instead: a 10 ms window
    counts as speech when it is within 38 dB of the loudest window and above -58 dBFS.
    The release tail keeps trailing consonants intact.
    """
    raw = run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000",
               "-f", "s16le", "-"]).stdout
    x = array.array("h"); x.frombytes(raw)
    win = 160
    db = []
    for i in range(0, len(x) - win, win):
        chunk = x[i:i + win]
        rms = math.sqrt(sum(v * v for v in chunk) / win) / 32768
        db.append(20 * math.log10(rms + 1e-9))
    if not db:
        return 0.0, len(x) / 16000
    floor = max(max(db) - 38, -58)
    voiced = [i for i, d in enumerate(db) if d > floor]
    if not voiced:
        return 0.0, len(x) / 16000
    total = len(x) / 16000
    start = max(0.0, voiced[0] * win / 16000 - lead)
    end = min(total, (voiced[-1] + 1) * win / 16000 + tail)
    return start, end


ENGINES = {"openrouter": tts_openrouter, "say": tts_say}


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _spell(n):
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else _ONES[n % 10])
    return str(n)


def flat(s):
    """Lowercase letters only, numerals spelled out, spacing ignored — so "YourApp"
    matches "Your App" and "week forty" matches "week 40"."""
    out, num = [], ""
    for ch in s.lower() + " ":
        if ch.isdigit():
            num += ch
            continue
        if num:
            out.append(_spell(int(num)))
            num = ""
        if ch.isalpha():
            out.append(ch)
    return "".join(out)


def matches(script, said):
    """True when the take says the scripted line. A model that answers instead of
    reading ("I'm sorry, I can't assist…") fails on both similarity and length."""
    a, b = flat(script), flat(said)
    if not a or not b or len(b) > len(a) * 1.6 + 6:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.8


def take(engine, text, voice, direction, attempts=4):
    """Natural-speed take, verified against the script, cached once verified."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(f"{engine}|{OR_MODEL}|{voice}|{direction}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(CACHE, f"{key}.wav")
    said_path = path + ".said.txt"
    if os.path.exists(path) and os.path.exists(said_path) and matches(text, open(said_path).read()):
        return path
    said = ""
    for n in range(1, attempts + 1):
        said = ENGINES[engine](text, voice, direction, path)
        if matches(text, said):
            with open(said_path, "w") as f:
                f.write(said)
            return path
        print(f"    take {n} for {text[:40]!r} said {said[:60]!r} — retrying")
    for f in (path, said_path):
        if os.path.exists(f):
            os.remove(f)
    raise SystemExit(f"Could not get a clean read of {text!r} after {attempts} takes "
                     f"(last: {said[:80]!r}). Rephrase the line.")


def main():
    ap = argparse.ArgumentParser(description="Render an optional voiceover track.")
    ap.add_argument("--script", default=os.path.join(ROOT, "voiceover.json"))
    ap.add_argument("--engine", choices=sorted(ENGINES), default=None,
                    help="default: openrouter if OPENROUTER_API_KEY is set, else say")
    ap.add_argument("--duration", type=float, default=33.0, help="film length in seconds")
    args = ap.parse_args()

    if not os.path.exists(args.script):
        raise SystemExit(f"No voiceover script at {args.script}. Voiceover is optional; see the docstring.")
    spec = json.load(open(args.script))
    lines = sorted(spec.get("lines", []), key=lambda l: l["at"])
    if not lines:
        raise SystemExit("voiceover.json has no lines.")
    engine = args.engine or ("openrouter" if os.environ.get("OPENROUTER_API_KEY") else "say")
    voice = spec.get("voice") or ("coral" if engine == "openrouter" else "Samantha")
    if engine == "say" and voice in OPENROUTER_VOICES:
        print(f"  note: '{voice}' is an OpenRouter voice; using macOS 'Samantha' for --engine say")
        voice = "Samantha"
    direction = spec.get("direction", "Clear, warm, confident product-ad delivery.")
    for b in ("ffmpeg", "ffprobe") + (("curl",) if engine == "openrouter" else ()):
        if shutil.which(b) is None:
            raise SystemExit(f"Missing required tool on PATH: {b}")

    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".wav") or f == "manifest.json":
            os.remove(os.path.join(OUT, f))

    print(f"Voiceover · engine={engine} · voice={voice} · {len(lines)} lines")
    manifest, problems = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for i, line in enumerate(lines):
            nxt = lines[i + 1]["at"] if i + 1 < len(lines) else args.duration
            budget = max(0.6, nxt - line["at"] - (MARGIN if i + 1 < len(lines) else 0.2))
            src = take(engine, line["text"], voice, direction)
            trimmed = os.path.join(tmp, f"t{i}.wav")
            a, b = speech_bounds(src)
            run(["ffmpeg", "-y", "-i", src, "-af", f"atrim=start={a:.3f}:end={b:.3f},asetpts=N/SR/TB",
                 "-ar", "48000", "-ac", "2", trimmed])
            natural = duration(trimmed)
            tempo = min(MAX_TEMPO, natural / budget) if natural > budget else 1.0
            final = natural / tempo
            over = final > budget + 0.05
            problems += over
            af = "loudnorm=I=-16:TP=-1.5:LRA=7"
            if tempo > 1.001:
                af = f"atempo={tempo:.4f},{af}"
            dest = os.path.join(OUT, f"{i:02d}.wav")
            run(["ffmpeg", "-y", "-i", trimmed, "-af", af, "-ar", "48000", "-ac", "2", dest])
            manifest.append({"file": f"{i:02d}.wav", "at": line["at"], "seconds": round(final, 3),
                             "text": line["text"]})
            flag = "  <- OVER WINDOW: shorten this line" if over else ""
            print(f"  {i:02d} @{line['at']:5.2f}s  {final:4.2f}s / {budget:4.2f}s  x{tempo:.2f}  {line['text'][:48]}{flag}")

    json.dump({"engine": engine, "voice": voice, "lines": manifest},
              open(os.path.join(OUT, "manifest.json"), "w"), indent=2)
    print(f"Wrote {len(manifest)} lines to {OUT}")
    if problems:
        print(f"{problems} line(s) overrun their scene. Shorten them; do not push the tempo further.")
        sys.exit(2)


if __name__ == "__main__":
    main()
