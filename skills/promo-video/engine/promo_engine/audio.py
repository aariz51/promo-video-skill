"""Sound mix: mapped effects + voiceover → one master WAV. Never background music.

Inputs come only from `render-config.json` (sound cues + the audio policy) and the
voiceover manifest. The policy decides what may enter the mix:

  voiceover  effects + voice, effects side-chain ducked beneath the voice
  effects    effects only; any voice files on disk are ignored, not mixed
  silent     no master at all; the film renders muted (no audio stream)

Effects are synthesised by `sfx_synth.py`. An optional ambience layer is procedural pink
noise, low-passed: non-melodic by construction. `audio-manifest.json` records the policy
and every source that went into the master, so QA can prove what is (and is not) in it.
"""
from __future__ import annotations

import json
import os
import tempfile

from . import sfx_synth, sound
from .config import Workspace
from .util import PromoError, media_duration, require_tools, run, write_json


def policy(rc: dict) -> dict:
    """The audio policy compiled into render-config.json (v4 configs: narration + effects)."""
    p = rc.get("audioPolicy")
    if p is None:
        vo = bool(rc["narration"]["enabled"])
        p = {"mode": "voiceover" if vo else "effects", "voiceover": vo, "soundEffects": True, "music": False}
    if p.get("music") is not False:
        raise PromoError("render-config.json asks for music; background music is never used",
                         hint="re-run `promo compile`")
    return p


def _max_db(path: str) -> float:
    res = run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"], check=False)
    for ln in res.stderr.splitlines():
        if "max_volume" in ln:
            return float(ln.split("max_volume:")[1].replace("dB", "").strip())
    return -99.0


def _norm_sfx(tmp: str, lib: dict, name: str, target: float = -3.0) -> str:
    """Peak-normalise one effect to `target` dBFS, 48 kHz stereo (once per run)."""
    src = lib[name]
    dst = os.path.join(tmp, f"sfx_{name}.wav")
    if not os.path.exists(dst):
        gain = target - _max_db(str(src))
        run(["ffmpeg", "-y", "-i", str(src), "-af", f"volume={gain:.2f}dB", "-ar", "48000", "-ac", "2", dst])
    return dst


def load_vo(ws: Workspace) -> list[dict]:
    manifest = ws.vo_dir / "manifest.json"
    if not manifest.exists():
        return []
    lines = json.loads(manifest.read_text()).get("lines", [])
    for ln in lines:
        if not (ws.vo_dir / ln["file"]).is_file():
            raise PromoError(f"voiceover manifest lists {ln['file']} but it is missing", hint="re-run `promo voice`")
    return lines


def _manifest_path(ws: Workspace):
    return ws.root / "build" / "audio-manifest.json"


def build_master(ws: Workspace, rc: dict) -> dict:
    pol = policy(rc)
    dur = float(rc["duration"])
    if pol["mode"] == "silent":
        # Nothing is generated and nothing stale may survive to be attached at render time.
        if ws.master_audio.exists():
            ws.master_audio.unlink()
        manifest = {"master": None, "duration": dur, "policy": pol, "music": False, "sources": []}
        write_json(_manifest_path(ws), manifest)
        return manifest
    require_tools("ffmpeg", "ffprobe")
    cues = rc["sound"]["cues"] if pol["soundEffects"] else []
    for name in sorted({c["fx"] for c in cues}):
        if name not in sound.LIBRARY:
            raise PromoError(f"cue uses unknown effect '{name}'")
    lib = sfx_synth.build_library(ws.root / "build" / "sfx") if cues else {}
    vo = load_vo(ws) if pol["voiceover"] else []
    if pol["voiceover"] and rc["narration"]["enabled"] and not vo:
        raise PromoError("the timeline has narration but no voiceover was rendered", hint="run `promo voice` first")
    ws.master_audio.parent.mkdir(parents=True, exist_ok=True)
    provenance: list[dict] = []
    lengths: dict[str, float] = {}

    with tempfile.TemporaryDirectory() as tmp:
        inputs = ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={dur}"]
        filt, fx_labels, vo_labels, idx = [], ["0:a"], [], 1
        if rc["sound"].get("ambience"):
            amb = os.path.join(tmp, "ambience.wav")
            run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anoisesrc=color=pink:amplitude=0.08:duration={dur}:seed=7",
                 "-af", f"lowpass=f=420,highpass=f=80,volume=0.06,afade=t=in:st=0:d=2,afade=t=out:st={max(0, dur - 2)}:d=2",
                 "-ar", "48000", "-ac", "2", amb])
            inputs += ["-i", amb]
            fx_labels.append(f"{idx}:a")
            idx += 1
            provenance.append({"kind": "ambience", "source": "procedural pink noise (non-melodic)", "at": 0, "seconds": dur})
        for c in cues:
            path = _norm_sfx(tmp, lib, c["fx"])
            if path not in lengths:
                lengths[path] = round(media_duration(path), 3)
            inputs += ["-i", path]
            d = int(c["at"] * 1000)
            filt.append(f"[{idx}:a]adelay={d}|{d},volume={c['vol']:.3f}[f{idx}]")
            fx_labels.append(f"f{idx}")
            provenance.append({"kind": "sfx", "source": sound.source_name(c["fx"]), "fx": c["fx"], "at": c["at"],
                               "seconds": lengths[path], "scene": c.get("scene")})
            idx += 1
        for ln in vo:
            path = str(ws.vo_dir / ln["file"])
            inputs += ["-i", path]
            d = int(ln["at"] * 1000)
            filt.append(f"[{idx}:a]adelay={d}|{d}[v{idx}]")
            vo_labels.append(f"v{idx}")
            provenance.append({"kind": "voice", "source": f"audio/vo/{ln['file']}", "at": ln["at"],
                               "seconds": ln["seconds"], "scene": ln.get("scene")})
            idx += 1
        filt.append("".join(f"[{l}]" for l in fx_labels)
                    + f"amix=inputs={len(fx_labels)}:normalize=0:dropout_transition=0[fx]")
        if vo_labels:
            filt.append("".join(f"[{l}]" for l in vo_labels)
                        + f"amix=inputs={len(vo_labels)}:normalize=0:dropout_transition=0,apad=whole_dur={dur}[vo]")
            filt.append("[vo]asplit=2[vo_key][vo_out]")
            # Fast attack, gentle release: a click still reads between words but never masks one.
            filt.append("[fx][vo_key]sidechaincompress=threshold=0.02:ratio=5:attack=8:release=260[fxd]")
            filt.append("[fxd]volume=0.8[fxd2]")
            filt.append("[fxd2][vo_out]amix=inputs=2:normalize=0:dropout_transition=0,alimiter=limit=0.89:level=disabled[out]")
        else:
            filt.append("[fx]alimiter=limit=0.89:level=disabled[out]")
        # Inline graph: `-filter_complex_script` is gone in ffmpeg 7+, and `-/filter_complex`
        # does not exist before 7. A film's graph is a few tens of KB, far under ARG_MAX.
        run(["ffmpeg", "-y"] + inputs + ["-filter_complex", ";".join(filt), "-map", "[out]",
                                         "-t", str(dur), "-ar", "48000", "-ac", "2", str(ws.master_audio)])

    manifest = {"master": "audio/master.wav", "duration": dur, "policy": pol, "music": False,
                "synth": f"sfx_synth v{sfx_synth.VERSION} ({sfx_synth.recipe_hash()})", "sources": provenance}
    write_json(_manifest_path(ws), manifest)
    return manifest
