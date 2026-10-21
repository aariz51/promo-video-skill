"""Voiceover: one narration line per cue, fitted to its window and verified.

Runs only when the audio policy has voice-over. In `effects` and `silent` modes no engine
is called, nothing is sent anywhere, and the manifest records why.

Providers (config `voice.provider`, resolved by `providers.pick`, never substituted):
  openrouter  openai/gpt-audio via OpenRouter (chat completions with audio output). The
              model's audio output modality is checked against OpenRouter's model list first.
  openai      OpenAI's speech endpoint (gpt-4o-mini-tts); each take is transcribed with
              gpt-4o-mini-transcribe and compared with the script.
  say         macOS `say`: keyless and offline.
  files       your own recordings: promo/assets/vo/NN.wav, one per narration line, in order.
  auto        the single configured API provider; ambiguity or absence is an error.

Keys are read ONLY from OPENROUTER_API_KEY / OPENAI_API_KEY, passed to curl on stdin
(never on the command line), and never written to disk or logged; error text is redacted.

Chat-style TTS models sometimes *answer* a line instead of reading it ("Scan any label."
once came back as "I'm sorry, I can't assist with that"). Each take's transcript is
compared with the script and retried; a line that never reads cleanly stops the run.
Takes are cached in promo/build/vo-cache under a key over every input that changes the
audio (provider, model, voice, direction, text, format, pipeline version).
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

from . import providers
from .util import PromoError, redact

OR_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OR_MODELS = "https://openrouter.ai/api/v1/models"
OR_MODEL = "openai/gpt-audio"
OA_SPEECH = "https://api.openai.com/v1/audio/speech"
OA_TRANSCRIBE = "https://api.openai.com/v1/audio/transcriptions"
OA_TTS_MODEL = "gpt-4o-mini-tts"
OA_STT_MODEL = "gpt-4o-mini-transcribe"
OA_TTS_MODELS = {"gpt-4o-mini-tts", "tts-1", "tts-1-hd"}  # the speech endpoint's models
OA_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse"}
PIPELINE = 2  # bump when trimming/format handling changes what a cached take contains
MODELS = {"openrouter": OR_MODEL, "openai": OA_TTS_MODEL, "say": "say", "files": "files"}
MAX_TEMPO = 1.2
OPENROUTER_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse", "marin", "cedar"}
MARGIN = 0.12  # breath left before the next line starts


def run(cmd, **kw):  # noqa: D401 - local variant keeps bytes I/O for audio
    res = subprocess.run(cmd, capture_output=True, **kw)
    if res.returncode != 0:
        err = res.stderr.decode(errors="replace") if isinstance(res.stderr, bytes) else res.stderr
        raise PromoError(f"{cmd[0]} failed (exit {res.returncode}):\n  " + redact("\n  ".join(err.strip().splitlines()[-5:])))
    return res


def _key(var):
    key = os.environ.get(var, "").strip()
    if not key:
        raise PromoError(f"{var} is not set", hint="export it in your shell; keys are never read from files or chat")
    return key


def _curl_auth(key):
    # Key goes through curl's stdin config so it never appears in `ps` output or argv.
    return f'header = "Authorization: Bearer {key}"\n'.encode()


def check_openrouter_model(model=OR_MODEL):
    """OpenRouter serves many models; confirm this one can actually produce audio."""
    res = run(["curl", "-sS", "--max-time", "30", OR_MODELS], text=True)
    try:
        models = json.loads(res.stdout).get("data", [])
    except json.JSONDecodeError as exc:
        raise PromoError("could not read OpenRouter's model list to verify audio support") from exc
    m = next((x for x in models if x.get("id") == model), None)
    if m is None:
        raise PromoError(f"OpenRouter does not list the model '{model}'", hint="check voice settings")
    outs = ((m.get("architecture") or {}).get("output_modalities")) or []
    if "audio" not in outs:
        raise PromoError(f"OpenRouter model '{model}' does not produce audio (outputs: {', '.join(outs) or 'unknown'})")


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", path], text=True).stdout
    return float(out.strip())


def tts_openrouter(text, voice, direction, dest):
    key = _key("OPENROUTER_API_KEY")
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
    res = run(["curl", "-sS", "-N", "-X", "POST", OR_ENDPOINT, "--config", "-",
               "-H", "Content-Type: application/json", "--data-binary", body],
              input=_curl_auth(key))
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
            raise PromoError(redact(f"OpenRouter error: {obj['error'].get('message', obj['error'])}"))
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


def _json_error(raw, who):
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    err = obj.get("error") if isinstance(obj, dict) else None
    if err:
        return PromoError(redact(f"{who} error: {err.get('message', err) if isinstance(err, dict) else err}"))
    return None


def transcribe_openai(path, key):
    res = run(["curl", "-sS", "--max-time", "60", "-X", "POST", OA_TRANSCRIBE, "--config", "-",
               "-F", f"model={OA_STT_MODEL}", "-F", "response_format=json", "-F", f"file=@{path}"],
              input=_curl_auth(key))
    err = _json_error(res.stdout, "OpenAI transcription")
    if err:
        raise err
    try:
        return json.loads(res.stdout).get("text", "")
    except json.JSONDecodeError as exc:
        raise PromoError("OpenAI transcription returned something that is not JSON") from exc


def tts_openai(text, voice, direction, dest):
    """Speech endpoint → WAV, then a transcription of the take for verification."""
    key = _key("OPENAI_API_KEY")
    if OA_TTS_MODEL not in OA_TTS_MODELS:
        raise PromoError(f"'{OA_TTS_MODEL}' is not an OpenAI speech model")
    body = {"model": OA_TTS_MODEL, "voice": voice, "input": text, "response_format": "wav"}
    if OA_TTS_MODEL == "gpt-4o-mini-tts":
        body["instructions"] = direction  # only this model accepts delivery instructions
    raw = dest + ".oa.wav"
    res = run(["curl", "-sS", "--max-time", "120", "-X", "POST", OA_SPEECH, "--config", "-",
               "-H", "Content-Type: application/json", "--data-binary", json.dumps(body), "-o", raw],
              input=_curl_auth(key))
    data = Path(raw).read_bytes() if os.path.exists(raw) else b""
    if not data.startswith(b"RIFF"):
        if os.path.exists(raw):
            os.remove(raw)
        raise _json_error(data, "OpenAI speech") or PromoError(f"No audio came back for {text!r}.")
    run(["ffmpeg", "-y", "-i", raw, "-ar", "48000", "-ac", "2", dest])
    os.remove(raw)
    return transcribe_openai(dest, key)


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


ENGINES = {"openrouter": tts_openrouter, "openai": tts_openai, "say": tts_say}


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


def cache_key(engine, text, voice, direction):
    """Every input that changes the audio. Line position is deliberately not one of them."""
    parts = [engine, MODELS[engine], voice or "", direction or "", text, "wav-48k-stereo", str(PIPELINE)]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()[:20]


def take(engine, text, voice, direction, cache, attempts=4):
    """Natural-speed take, verified against the script, cached once verified."""
    os.makedirs(cache, exist_ok=True)
    key = cache_key(engine, text, voice, direction)
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



DEFAULT_VOICES = {"openrouter": "cedar", "openai": "coral", "say": "Samantha", "files": None}


def _voice_for(engine, configured):
    v = configured or DEFAULT_VOICES[engine]
    if engine == "say" and v in OPENROUTER_VOICES | OA_VOICES:
        return DEFAULT_VOICES["say"]
    if engine == "openai" and v not in OA_VOICES:
        raise PromoError(f"OpenAI has no voice '{v}'", hint=f"use one of {', '.join(sorted(OA_VOICES))}")
    if engine == "openrouter" and v not in OPENROUTER_VOICES:
        raise PromoError(f"OpenRouter gpt-audio has no voice '{v}'", hint=f"use one of {', '.join(sorted(OPENROUTER_VOICES))}")
    return v


def render_voice(ws, rc: dict, cfg: dict) -> dict:
    """Render every narration line in render-config.json into build/public/audio/vo/."""
    lines = rc["narration"]["lines"]
    out = Path(ws.vo_dir)
    out.mkdir(parents=True, exist_ok=True)

    def clear():
        for f in out.iterdir():
            if f.suffix == ".wav" or f.name == "manifest.json":
                f.unlink()

    policy_on = bool(cfg["audio"]["voiceover"]) and (rc.get("audioPolicy") or {}).get("voiceover", True)
    if not policy_on or not rc["narration"]["enabled"]:
        # No engine is called and no request leaves the machine.
        clear()
        reason = rc["narration"]["reason"] or "narration disabled"
        manifest = {"engine": "none", "reason": reason, "lines": []}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
        return manifest
    if not lines:
        raise PromoError("narration is enabled but render-config.json has no narration lines")
    engine = providers.pick(cfg)  # raises rather than substituting
    for b in ("ffmpeg", "ffprobe") + (("curl",) if engine in ("openrouter", "openai") else ()):
        if shutil.which(b) is None:
            raise PromoError(f"missing required tool on PATH: {b}")
    voice = _voice_for(engine, cfg["voice"].get("voice"))
    direction = cfg["voice"]["direction"]
    cache = str(Path(ws.root) / "build" / "vo-cache")
    if engine == "openrouter" and any(not os.path.exists(os.path.join(cache, cache_key(engine, ln["text"], voice, direction) + ".wav"))
                                      for ln in lines):
        check_openrouter_model()
    clear()
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
