"""Voiceover: one narration line per cue, fitted to its window and verified.

Providers (config `voice.provider`):
  auto        openrouter when OPENROUTER_API_KEY is set, else macOS `say`, else fail loudly
  openrouter  openai/gpt-audio via OpenRouter. The key is read ONLY from the
              OPENROUTER_API_KEY environment variable, passed to curl on stdin (never on the
              command line) and never written to disk or logged.
  say         macOS `say`: keyless and offline.
  files       your own recordings: promo/assets/vo/NN.wav, one per narration line, in order.
  none        no narration (only valid when timeline.json disables narration with a reason).

Chat-style TTS models sometimes *answer* a line instead of reading it ("Scan any label."
once came back as "I'm sorry, I can't assist with that"). Each take's transcript is
compared with the script and retried; a line that never reads cleanly stops the run.
Takes are cached in promo/build/vo-cache, so re-runs are free and deterministic.
"""
import array
import base64
import difflib
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .util import PromoError

OR_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "openai/gpt-audio"
MAX_TEMPO = 1.2
OPENROUTER_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"}
MARGIN = 0.12  # breath left before the next line starts


def run(cmd, **kw):  # noqa: D401 - local variant keeps bytes I/O for audio
    res = subprocess.run(cmd, capture_output=True, **kw)
    if res.returncode != 0:
        err = res.stderr.decode(errors="replace") if isinstance(res.stderr, bytes) else res.stderr
        raise PromoError(f"{cmd[0]} failed (exit {res.returncode}):\n  " + "\n  ".join(err.strip().splitlines()[-5:]))
    return res


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path], text=True).stdout
    return float(out.strip())


def tts_openrouter(text, voice, direction, dest):
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise PromoError(
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
            raise PromoError(f"OpenRouter error: {obj['error'].get('message', obj['error'])}")
        delta = (obj.get("choices") or [{}])[0].get("delta") or {}
        audio = delta.get("audio") or {}
        if audio.get("data"):
            pcm += base64.b64decode(audio["data"])
        if audio.get("transcript"):
            said += audio["transcript"]
    if len(pcm) < 4000:
        raise PromoError(f"No audio came back for {text!r}. Check the key and the voice name.")
    raw = dest + ".pcm"
    with open(raw, "wb") as f:
        f.write(pcm)
    run(["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
         "-ar", "48000", "-ac", "2", dest])
    os.remove(raw)
    return said


def tts_say(text, voice, _direction, dest):
    if shutil.which("say") is None:
        raise PromoError("--engine say needs macOS. Use --engine openrouter, or record the lines yourself.")
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


def take(engine, text, voice, direction, cache, attempts=4):
    """Natural-speed take, verified against the script, cached once verified."""
    os.makedirs(cache, exist_ok=True)
    key = hashlib.sha1(f"{engine}|{OR_MODEL}|{voice}|{direction}|{text}".encode()).hexdigest()[:16]
    path = os.path.join(cache, f"{key}.wav")
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
    raise PromoError(f"Could not get a clean read of {text!r} after {attempts} takes "
                     f"(last: {said[:80]!r}). Rephrase the line.")




def pick_engine(provider: str) -> str:
    if provider == "auto":
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if shutil.which("say"):
            return "say"
        raise PromoError("no voiceover engine is available on this machine",
                         hint="set OPENROUTER_API_KEY, record lines into promo/assets/vo/ and use provider "
                              "'files', or disable narration in timeline.json with a reason")
    return provider


def render_voice(ws, rc: dict, cfg: dict) -> dict:
    """Render every narration line in render-config.json into build/public/audio/vo/."""
    lines = rc["narration"]["lines"]
    out = Path(ws.vo_dir)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.iterdir():
        if f.suffix == ".wav" or f.name == "manifest.json":
            f.unlink()
    if not rc["narration"]["enabled"] or cfg["voice"]["provider"] == "none":
        if rc["narration"]["enabled"]:
            raise PromoError("voice provider is 'none' but the timeline has narration",
                             hint="choose a provider, or set narration.enabled=false with a reason in timeline.json")
        manifest = {"engine": "none", "reason": rc["narration"]["reason"], "lines": []}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return manifest
    if not lines:
        raise PromoError("narration is enabled but render-config.json has no narration lines")
    engine = pick_engine(cfg["voice"]["provider"])
    for b in ("ffmpeg", "ffprobe") + (("curl",) if engine == "openrouter" else ()):
        if shutil.which(b) is None:
            raise PromoError(f"missing required tool on PATH: {b}")
    voice = cfg["voice"].get("voice") or ("cedar" if engine == "openrouter" else "Samantha")
    if engine == "say" and voice in OPENROUTER_VOICES:
        voice = "Samantha"
    direction = cfg["voice"]["direction"]
    cache = str(Path(ws.root) / "build" / "vo-cache")
    manifest, problems = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for i, line in enumerate(lines):
            budget = max(0.6, line["windowEnd"] - line["at"])
            if engine == "files":
                src = Path(ws.assets) / "vo" / f"{i:02d}.wav"
                if not src.is_file():
                    raise PromoError(f"voice provider 'files' needs {src} for line {i}: {line['text']!r}")
                src = str(src)
            else:
                src = take(engine, line["text"], voice, direction, cache)
            trimmed = os.path.join(tmp, f"t{i}.wav")
            a, b = speech_bounds(src)
            run(["ffmpeg", "-y", "-i", src, "-af", f"atrim=start={a:.3f}:end={b:.3f},asetpts=N/SR/TB",
                 "-ar", "48000", "-ac", "2", trimmed])
            natural = duration(trimmed)
            tempo = min(MAX_TEMPO, natural / budget) if natural > budget else 1.0
            final = natural / tempo
            if final > budget + 0.05:
                problems.append(f"line {i} ({line['scene']}) needs {final:.2f}s but has {budget:.2f}s: {line['text']!r}")
            af = "loudnorm=I=-16:TP=-1.5:LRA=7"
            if tempo > 1.001:
                af = f"atempo={tempo:.4f},{af}"
            dest = out / f"{i:02d}.wav"
            run(["ffmpeg", "-y", "-i", trimmed, "-af", af, "-ar", "48000", "-ac", "2", str(dest)])
            manifest.append({"file": dest.name, "at": line["at"], "seconds": round(final, 3),
                             "windowEnd": line["windowEnd"], "scene": line["scene"], "text": line["text"],
                             "tempo": round(tempo, 3)})
            print(f"  vo {i:02d} @{line['at']:6.2f}s  {final:4.2f}s / {budget:4.2f}s  x{tempo:.2f}  {line['text'][:56]}")
    data = {"engine": engine, "voice": voice, "lines": manifest}
    (out / "manifest.json").write_text(json.dumps(data, indent=2))
    if problems:
        raise PromoError("narration overruns its scene:\n  " + "\n  ".join(problems),
                         hint="shorten those lines in timeline.json; the tempo is never pushed past 1.2x")
    return data
