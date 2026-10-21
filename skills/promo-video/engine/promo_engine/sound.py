"""Sound design: deterministic cues tied to on-screen events. No music, by construction.

The library below is the complete set of sounds the mixer can use: the effects synthesised
by `sfx_synth.py` (original, no third-party samples). Every one is a short effect; nothing
melodic or long enough to act as a music bed exists in it (QA re-checks the durations of
whatever was mixed).
"""
from __future__ import annotations

from .sfx_synth import RECIPES

# Effect name → what it is for. The sound itself is a recipe in sfx_synth.RECIPES.
LIBRARY = {
    "click": "a tap or cursor press",
    "pop": "something lands",
    "pop2": "a lighter digital landing",
    "whoosh": "a camera move or push transition",
    "chime": "a result resolves",
    "type": "a keystroke",
    "tick": "a line of output, a counter step",
    "tick2": "a softer tick",
    "drag": "cards fanning out",
    "sparkle": "a light shimmer on a reveal",
    "riser": "tension into a reveal",
    "rise": "a short lift",
    "thud": "an impact on a freeze or landing",
    "kick": "a low hit",
    "dive": "a fall into detail",
    "ascent": "a rising resolve",
    "braam": "a cinematic low impact",
}

# Relative loudness of each role. Interaction sounds sit forward; atmosphere sits back.
LEVEL = {"click": 0.9, "type": 0.55, "tick": 0.5, "tick2": 0.45, "pop": 0.6, "pop2": 0.55,
         "whoosh": 0.5, "chime": 0.6, "sparkle": 0.45, "riser": 0.45, "rise": 0.4, "thud": 0.75,
         "kick": 0.6, "dive": 0.5, "ascent": 0.45, "drag": 0.5, "braam": 0.55}

MAX_EFFECT_SECONDS = 6.0
assert set(LIBRARY) == set(RECIPES), "every cue name needs a synthesis recipe"


def source_name(fx: str) -> str:
    """How an effect is recorded in the audio manifest (and allow-listed by QA)."""
    return f"sfx/{fx}.wav"


def cue(fx: str, at: float, vol: float | None = None, scene: str | None = None, why: str = "") -> dict:
    return {"fx": fx, "at": round(max(0.0, at), 3), "vol": round(vol if vol is not None else LEVEL[fx], 3),
            "scene": scene, "why": why}


def transition_cues(kind: str, cut_at: float, scene: str) -> list[dict]:
    if kind == "light":
        return [cue("riser", cut_at - 1.1, scene=scene, why="tension into a light transition"),
                cue("sparkle", cut_at, 0.35, scene, "light bloom peaks")]
    if kind in ("push", "zoom"):
        return [cue("whoosh", cut_at - 0.2, scene=scene, why=f"{kind} transition")]
    if kind == "wipe":
        return [cue("whoosh", cut_at - 0.1, 0.4, scene, "typography wipe")]
    return []


def scene_cues(scene: dict, start: float) -> list[dict]:
    """Cues for the events the timeline engine scheduled inside one scene."""
    k, sid, t = scene["kind"], scene["id"], scene["props"].get("_t", {})
    out: list[dict] = []
    if k == "hook":
        out.append(cue("rise", start + 0.2, 0.3, sid, "the point of light appears"))
        out.append(cue("riser", start + t["freeze"] - 1.6, 0.4, sid, "fragments accelerate"))
        out.append(cue("thud", start + t["freeze"], scene=sid, why="everything freezes"))
    elif k == "wordzoom":
        n = max(1, int(t["typeFor"] / 0.09))
        out += [cue("type", start + 0.3 + i * t["typeFor"] / n, scene=sid, why="keystroke") for i in range(min(n, 24))]
        if "then" in t:
            out += [cue("type", start + t["then"] + i * 0.08, scene=sid, why="retype") for i in range(6)]
        out.append(cue("click", start + t["select"], 0.7, sid, "the word is selected"))
        out.append(cue("whoosh", start + t["zoom"][0] + 0.3, 0.55, sid, "fly through the letter"))
        out.append(cue("thud", start + t["zoom"][1], 0.6, sid, "arrive on the ground"))
    elif k == "title":
        out.append(cue("thud", start + t["name"], 0.5, sid, "the name lands"))
        out.append(cue("sparkle", start + t["name"] + 0.15, 0.3, sid, "light sweep"))
    elif k == "pillars":
        out += [cue("pop", start + x, scene=sid, why="pillar lands") for x in t["items"]]
    elif k == "screen":
        if scene["props"].get("camera", "push") != "hold":
            out.append(cue("whoosh", start + 0.05, 0.3, sid, "camera move"))
        out += [cue("pop2", start + x, scene=sid, why="callout appears") for x in t.get("callouts", [])]
        if "click" in t:
            out.append(cue("click", start + t["click"], scene=sid, why="cursor press"))
    elif k == "flow":
        steps = t["steps"]
        out += [cue("pop", start + x, scene=sid, why="step activates") for x in steps[:-1]]
        out.append(cue("chime", start + steps[-1], scene=sid, why="result resolves"))
    elif k == "terminal":
        for ln in t["lines"]:
            if ln["type"] == "cmd":
                n = max(1, int(ln["typeFor"] / 0.09))
                out += [cue("type", start + ln["at"] + i * ln["typeFor"] / n, scene=sid, why="keystroke")
                        for i in range(min(n, 24))]
            elif ln["type"] == "ok":
                out.append(cue("chime", start + ln["at"], 0.45, sid, "success line"))
            else:
                out.append(cue("tick2", start + ln["at"], 0.35, sid, "output line"))
    elif k == "document":
        out += [cue("tick", start + x, 0.4, sid, "section writes in") for x in t["sections"]]
    elif k == "montage":
        out.append(cue("drag", start + t["items"][0], scene=sid, why="cards fan out"))
    elif k == "compare":
        out.append(cue("pop", start + t["left"], scene=sid, why="first path"))
        out.append(cue("pop", start + t["right"], scene=sid, why="second path"))
        if "verdict" in t:
            out.append(cue("chime", start + t["verdict"], 0.5, sid, "verdict"))
    elif k == "metric":
        a, b = t["count"]
        steps = 8
        out += [cue("tick", start + a + (b - a) * i / steps, 0.35, sid, "count") for i in range(steps)]
        out.append(cue("thud", start + b, 0.6, sid, "value lands"))
    elif k == "lockup":
        out.append(cue("sparkle", start + t["name"], 0.4, sid, "name resolves"))
        out.append(cue("ascent", start + t["name"] - 0.4, 0.3, sid, "final resolve"))
    return out
