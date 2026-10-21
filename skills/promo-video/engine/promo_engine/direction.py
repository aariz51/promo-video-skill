"""CREATIVE_DIRECTION.md and the reference-derived storyboard.

Mode B (reference):
  `scaffold(ws)`     writes CREATIVE_DIRECTION.md from reference/breakdown.json: one section
                     per measured scene with the twenty breakdown fields (measured values
                     prefilled and labelled `measured:`), a transition table, the measured
                     motion language, and the decision record. The agent replaces every TODO
                     after reading the frames; `check(...)` holds it to that contract.
  `storyboard(ws)`   writes a timeline.json skeleton whose scene count, scene lengths
                     (scaled to the target runtime) and transitions come from the reference.
  `structure_check`  run by `promo check timeline` in Mode B: the finished timeline must keep
                     the reference's structure, or declare each departure.

Mode A (autonomous):
  `write_autonomous` assembles CREATIVE_DIRECTION.md from creative-prompt.md and the compiled
                     storyboard, so both modes deliver the same document.
"""
from __future__ import annotations

import re
from pathlib import Path

from .artifacts import PLACEHOLDER, _strip_comments, copied_phrases, sections
from .config import Workspace, mode, reference_source
from .util import PromoError, Report, fmt_time, read_json, write_json

HEADER_B = "# CREATIVE DIRECTION — reference-driven"
HEADER_A = "# CREATIVE DIRECTION — autonomous"
FIELDS = [
    "Scene ID", "Start", "End", "Duration", "Evidence frames", "On screen", "Background and colour",
    "Composition and placement", "Typography and text animation", "Camera movement",
    "Object movement and animation", "Entrance and exit", "Transition technique", "Pacing and hold",
    "Visual hierarchy", "Audio and sound cues", "Narrative function", "Signature device",
    "Confidence and ambiguity", "Adaptation to the product",
]
MOTION_LABELS = ["Overall pace", "Beat intervals", "Scene-duration distribution", "Cut density",
                 "Camera vocabulary", "Transition vocabulary", "Typography behaviour", "Depth and parallax",
                 "Acceleration and deceleration", "Signature devices", "Opening convention",
                 "Ending convention", "Continuity rules"]
DECISIONS = ["From the reference", "From the product", "Deliberately changed", "Must stay recognisable",
             "Why this adaptation fits"]
TRANSITION_COLUMNS = ["ID", "From → To", "Start", "End", "Measured technique", "What moves", "Direction",
                      "Carries an element across", "Narrative role", "Remotion implementation"]
# Measured reference transition → the renderer's transition that reproduces it.
TRANSITION_MAP = {"cut": "cut", "flash": "dip", "dissolve": "fade", "dip-black": "dip", "dip-white": "dip",
                  "wipe-left": "wipe", "wipe-right": "wipe", "wipe-up": "wipe", "wipe-down": "wipe",
                  "gradual": "fade"}
DURATION_TOLERANCE = 0.35  # a timeline scene may differ from its scaled reference scene by ±35%
RUNTIME_TOLERANCE = 0.20


def load_breakdown(ws: Workspace) -> dict:
    p = ws.reference_dir / "breakdown.json"
    if not p.exists():
        raise PromoError("there is no measured reference breakdown", hint="run `promo watch` first")
    return read_json(p)


def implementation(tr: dict) -> dict:
    """The timeline transition that reproduces a measured one."""
    kind = TRANSITION_MAP.get(tr["type"], "fade")
    out = {"type": kind, "duration": round(max(0.2, tr["duration"]), 2) if kind != "cut" else 0}
    if tr["type"].startswith("wipe-"):
        out["direction"] = tr["type"].split("-", 1)[1]
        out["sweep"] = False  # the measured wipe is a clean edge; no light sweep the reference lacks
    curve = (tr.get("detail") or {}).get("alpha") or (tr.get("detail") or {}).get("coverage")
    if kind in ("fade", "wipe") and curve:
        from .reference import easing_of
        if easing_of(curve):
            out["easing"] = easing_of(curve)  # the reference's speed profile, measured
    if tr["type"] in ("dip-black", "dip-white", "flash"):
        out["color"] = "white" if tr["type"] == "dip-white" else "black"
        if tr["type"] == "flash":
            out["duration"] = 0.2
    return out


# ── Mode B: CREATIVE_DIRECTION.md scaffold ─────────────────────────────────────────

def _fr(files: list[dict]) -> str:
    return "; ".join(f"`reference/{f['file']}` ({fmt_time(f['t'])})" for f in files)


def scaffold(ws: Workspace, *, force: bool = False) -> Path:
    if ws.direction.exists() and not force:
        raise PromoError(f"{ws.direction.name} already exists", hint="edit it, or pass --force to regenerate the scaffold")
    bd = load_breakdown(ws)
    cfg = ws.config()
    name = cfg["product"]["name"] or "the product"
    m, ms = bd["metadata"], bd["motionSpec"]
    out_tr = {t["from"]: t for t in bd["transitions"]}
    in_tr = {t["to"]: t for t in bd["transitions"]}
    L = [HEADER_B, "",
         f"Reference: {reference_source(cfg) or bd['source']} · measured by `promo watch` (analyzer v{bd['version']}, "
         f"fingerprint {bd['fingerprint']})",
         f"Product: {name}", "",
         "Every `measured:` value comes from the decoded file. Replace each TODO with what you see in the "
         "frames and contact sheets (`reference/sheets/`). Write what is visible first, then any interpretation "
         "marked `Interpretation:`. Do not name software, easing curves or keyframes the evidence cannot show.",
         "", "## REFERENCE", "",
         "| Property | Measured |", "|---|---|",
         f"| Duration | {m['duration']} s |", f"| Frame rate | {m['fps']} fps |",
         f"| Size / aspect | {m['width']}×{m['height']} ({m['aspect']}) |",
         f"| Audio | {'present (' + str(m['audio']['codec']) + ')' if m['audio']['present'] else 'none'} |",
         f"| Captions / transcript | {'yes' if m['captions'].get('available') else 'no'} — {m['captions'].get('source')} |",
         f"| Major scenes | {len(bd['scenes'])} |",
         f"| Contact sheets | {', '.join('`reference/' + s['file'] + '`' for s in bd['contactSheets'])} |",
         "", "## SCENE BREAKDOWN", ""]
    for sc in bd["scenes"]:
        me = sc["measured"]
        enter = in_tr.get(sc["id"])
        leave = out_tr.get(sc["id"])
        entrance = (f"measured: enters by {enter['id']} ({enter['type']}, {enter['duration']} s)" if enter
                    else "measured: opens the film" + (f"; {me['fade']}" if me.get("fade") else ""))
        exit_ = (f"exits by {leave['id']} ({leave['type']}, {leave['duration']} s)" if leave
                 else "closes the film" + (f"; {me['fade']}" if me.get("fade") and "out" in me["fade"] else ""))
        vals = {
            "Scene ID": sc["id"], "Start": fmt_time(sc["start"]), "End": fmt_time(sc["end"]),
            "Duration": f"{sc['duration']:.2f} s",
            "Evidence frames": _fr(sc["frames"]),
            "On screen": "TODO",
            "Background and colour": f"measured: mean {me['mean']}, palette "
                                     f"{', '.join(p['hex'] + ' ' + str(int(p['share'] * 100)) + '%' for p in me['palette'])}, "
                                     f"brightness {me['brightness']} · TODO",
            "Composition and placement": "TODO",
            "Typography and text animation": "TODO",
            "Camera movement": f"measured: {me['camera']} · TODO",
            "Object movement and animation": f"measured: motion energy {me['motionEnergy']} · TODO",
            "Entrance and exit": f"{entrance}; {exit_} · TODO",
            "Transition technique": (f"measured: out by {leave['id']} {leave['type']}" if leave else "measured: last scene")
                                    + " · TODO",
            "Pacing and hold": f"measured: {sc['duration']:.2f} s against a median of "
                               f"{ms['sceneDurations']['median']} s · TODO",
            "Visual hierarchy": "TODO",
            "Audio and sound cues": f"measured: audio track {'present' if m['audio']['present'] else 'absent'} · TODO",
            "Narrative function": "TODO",
            "Signature device": "TODO",
            "Confidence and ambiguity": "TODO",
            "Adaptation to the product": "TODO",
        }
        L += [f"### {sc['id']} · {fmt_time(sc['start'])}–{fmt_time(sc['end'])}", "", "| # | Field | Value |", "|---|---|---|"]
        L += [f"| {i} | {f} | {vals[f]} |" for i, f in enumerate(FIELDS, 1)]
        L.append("")
    L += ["## TRANSITIONS", "", "| " + " | ".join(TRANSITION_COLUMNS) + " |", "|" + "---|" * len(TRANSITION_COLUMNS)]
    for tr in bd["transitions"]:
        impl = implementation(tr)
        impl_s = impl["type"] + "".join(f" {k}={v}" for k, v in impl.items() if k not in ("type",))
        L.append(f"| {tr['id']} | {tr['from']} → {tr['to']} | {fmt_time(tr['start'])} | {fmt_time(tr['end'])} | "
                 f"measured: {tr['type']} ({tr['duration']} s) | TODO | "
                 f"{tr['type'].split('-', 1)[1] if tr['type'].startswith('wipe-') else 'TODO'} | TODO | TODO | {impl_s} |")
    q = ms["sceneDurations"]
    measured_motion = {
        "Overall pace": f"measured: {ms['sceneCount']} scenes in {ms['duration']} s, average {ms['averageScene']} s",
        "Beat intervals": "measured: " + ", ".join(f"{b:.2f}" for b in ms["beatIntervals"][:24]) + " s",
        "Scene-duration distribution": f"measured: min {q['min']} · p25 {q['p25']} · median {q['median']} · "
                                       f"p75 {q['p75']} · max {q['max']} s",
        "Cut density": f"measured: {ms['boundariesPerMinute']} boundaries/min; by quarter "
                       + ", ".join(str(x["perMinute"]) for x in ms["byQuarter"]),
        "Camera vocabulary": "measured: " + ", ".join(f"{k} ×{v}" for k, v in ms["cameraVocabulary"].items()),
        "Transition vocabulary": "measured: " + (", ".join(f"{k} ×{v}" for k, v in ms["transitionVocabulary"].items()) or "none"),
        "Opening convention": f"measured: {ms['opening']}",
        "Ending convention": f"measured: {ms['closing']}",
    }
    L += ["", "## MOTION LANGUAGE", "",
          "Turn each observation into a rule the build can follow (numbers, directions, durations), not adjectives.", ""]
    L += [f"- {lab}: {measured_motion[lab] + ' · TODO' if lab in measured_motion else 'TODO'}" for lab in MOTION_LABELS]
    L += ["", "## REUSABLE RULES", "",
          "10–20 numbered rules. Each cites the scene (S##), transition (T##) or timestamp that evidences it.", "",
          "1. TODO", "", "## ADAPTATION DECISIONS", ""]
    L += [f"- {d}: TODO" for d in DECISIONS]
    L += ["", "The reference is a structural and motion input only: no footage, logos, characters, script or "
          "distinctive assets from it are reused.", ""]
    ws.direction.write_text("\n".join(L))
    return ws.direction


# ── Mode B: validation ─────────────────────────────────────────────────────────────

def parse_rules(md: str) -> list[dict]:
    body = sections(_strip_comments(md)).get("REUSABLE RULES", "")
    out = []
    for ln in body.splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s+(?:(R\d+)\s*[—–:-]\s*)?(.+)$", ln)
        if m:
            out.append({"id": m.group(2) or f"R{m.group(1)}", "text": m.group(3).strip()})
    return out


def _scene_blocks(md: str) -> dict[str, str]:
    body = sections(_strip_comments(md)).get("SCENE BREAKDOWN", "")
    out, cur, buf = {}, None, []
    for ln in body.splitlines():
        m = re.match(r"^###\s+(S\d+)\b", ln)
        if m:
            if cur:
                out[cur] = "\n".join(buf)
            cur, buf = m.group(1), []
        elif cur:
            buf.append(ln)
    if cur:
        out[cur] = "\n".join(buf)
    return out


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("|") and not re.fullmatch(r"\|[\s|:-]*\|", s):
            rows.append([c.strip() for c in s.strip("|").split("|")])
    return rows[1:] if rows else rows  # drop the header row


def check(md: str, bd: dict, root: Path, transcript: list[str] | None = None) -> Report:
    from .timeline import TRANSITIONS
    r = Report()
    where = "CREATIVE_DIRECTION.md"
    if not md.lstrip().startswith(HEADER_B):
        r.error(where, f"must start with '{HEADER_B}'")
    body = _strip_comments(md)
    secs = sections(body)
    for want in ("REFERENCE", "SCENE BREAKDOWN", "TRANSITIONS", "MOTION LANGUAGE", "REUSABLE RULES", "ADAPTATION DECISIONS"):
        if want not in secs:
            r.error(where, f"missing section '## {want}'")
    blocks = _scene_blocks(md)
    ids = [s["id"] for s in bd["scenes"]]
    for sid in ids:
        if sid not in blocks:
            r.error(where, f"no breakdown for measured scene {sid}")
            continue
        rows = {row[1]: row[2] for row in _table_rows(blocks[sid]) if len(row) >= 3}
        for f in FIELDS:
            v = rows.get(f, "")
            if not v or PLACEHOLDER.search(v):
                r.error(where, f"{sid}: field '{f}' is not filled in")
            elif re.fullmatch(r"measured:[^·]*", v.strip()) and f not in ("Start", "End", "Duration", "Scene ID",
                                                                         "Evidence frames", "Transition technique"):
                r.error(where, f"{sid}: field '{f}' repeats the measurement without an observation")
        for ref in re.findall(r"`(reference/[^`]+)`", rows.get("Evidence frames", "")):
            if not (root / ref).is_file():
                r.error(where, f"{sid}: evidence frame {ref} does not exist")
        if not re.findall(r"`reference/[^`]+`", rows.get("Evidence frames", "")):
            r.error(where, f"{sid}: no evidence frames cited")
    for extra in set(blocks) - set(ids):
        r.error(where, f"breakdown section {extra} is not a measured scene")
    rows = _table_rows(secs.get("TRANSITIONS", ""))
    seen = set()
    for row in rows:
        if len(row) < len(TRANSITION_COLUMNS):
            r.error(where, f"transition row has {len(row)} columns, needs {len(TRANSITION_COLUMNS)}")
            continue
        tid = row[0]
        seen.add(tid)
        m = re.match(r"(S\d+)\s*→\s*(S\d+)", row[1])
        if not m or m.group(1) not in ids or m.group(2) not in ids:
            r.error(where, f"{tid}: From → To must name measured scenes")
        elif ids.index(m.group(2)) != ids.index(m.group(1)) + 1:
            r.error(where, f"{tid}: joins scenes that are not adjacent")
        if any(PLACEHOLDER.search(c) for c in row):
            r.error(where, f"{tid}: transition row has unfilled cells")
        impl = row[9].split()[0] if row[9].split() else ""
        if impl not in TRANSITIONS:
            r.error(where, f"{tid}: Remotion implementation '{impl}' is not a renderer transition ({', '.join(sorted(TRANSITIONS))})")
    for tr in bd["transitions"]:
        if tr["id"] not in seen:
            r.error(where, f"measured transition {tr['id']} is missing from TRANSITIONS")
    motion = secs.get("MOTION LANGUAGE", "")
    for lab in MOTION_LABELS:
        m = re.search(rf"^- {re.escape(lab)}:\s*(.*)$", motion, re.M)
        if not m or not m.group(1).strip() or PLACEHOLDER.search(m.group(1)):
            r.error(where, f"MOTION LANGUAGE '{lab}' is not filled in")
    rules = parse_rules(md)
    if not 10 <= len(rules) <= 20:
        r.error(where, f"REUSABLE RULES needs 10–20 numbered rules (found {len(rules)})")
    tids = {t["id"] for t in bd["transitions"]}
    for rule in rules:
        refs = set(re.findall(r"\b[ST]\d{2}\b", rule["text"]))
        stamps = re.findall(r"\b\d{1,2}:\d{2}(?:\.\d)?\b", rule["text"])
        if not refs and not stamps:
            r.error(where, f"rule {rule['id']} cites no scene, transition or timestamp")
        for ref in refs - set(ids) - tids:
            r.error(where, f"rule {rule['id']} cites {ref}, which was not measured")
    dec = secs.get("ADAPTATION DECISIONS", "")
    for d in DECISIONS:
        m = re.search(rf"^- {re.escape(d)}:\s*(.*)$", dec, re.M)
        if not m or not m.group(1).strip() or PLACEHOLDER.search(m.group(1)):
            r.error(where, f"ADAPTATION DECISIONS '{d}' is not filled in")
    if PLACEHOLDER.search(body):
        r.error(where, "unfilled placeholders (TODO) remain")
    if transcript:
        copied = copied_phrases(body, transcript)
        if copied:
            r.error(where, "copies the reference's narration verbatim: " + "; ".join(f"“{c}”" for c in copied[:3]))
    if re.search(r"\b(background music|music bed|soundtrack)\b", body, re.I) and not re.search(
            r"no (background )?music|never (uses )?music|music[^.\n]{0,40}(not used|excluded|dropped|removed)", body, re.I):
        r.error(where, "mentions music without excluding it; the film never uses background music")
    return r


# ── Mode B: storyboard skeleton and structural check ───────────────────────────────

def target_runtime(bd: dict, cfg: dict) -> float:
    """Mode B keeps the reference's length unless the user set a runtime."""
    if "runtime" in (cfg.get("decided") or []):
        lo, hi = cfg["duration"]["min"], cfg["duration"]["max"]
        return float(min(max(bd["metadata"]["duration"], lo), hi))
    return float(bd["metadata"]["duration"])


def spans(bd: dict) -> dict[str, float]:
    """Each measured scene's share of the clock: its own length plus the whole transition
    into it. The renderer plays a transition over the first frames of the incoming scene, so
    each scene then starts exactly where the reference's transition into it starts."""
    out = {}
    for sc in bd["scenes"]:
        tr_in = next((t for t in bd["transitions"] if t["to"] == sc["id"]), None)
        out[sc["id"]] = sc["duration"] + (tr_in["duration"] if tr_in else 0)
    return out


def storyboard(ws: Workspace, *, force: bool = False) -> Path:
    """timeline.json skeleton: one scene per measured scene, scaled, with mapped transitions."""
    if ws.timeline.exists() and not force:
        raise PromoError("timeline.json already exists", hint="pass --force to replace it with the reference skeleton")
    bd = load_breakdown(ws)
    cfg = ws.config()
    runtime = target_runtime(bd, cfg)
    k = runtime / bd["metadata"]["duration"]
    in_tr = {t["to"]: t for t in bd["transitions"]}
    share = spans(bd)
    scenes = []
    for sc in bd["scenes"]:
        tr = in_tr.get(sc["id"])
        entry = {"id": sc["id"].lower(), "ref": sc["id"], "kind": "TODO", "duration": round(max(0.5, share[sc["id"]] * k), 2),
                 "purpose": "TODO", "source": f"reference {sc['id']} {fmt_time(sc['start'])}–{fmt_time(sc['end'])}",
                 "props": {}, "refMotion": {"camera": sc["measured"]["camera"], "energy": sc["measured"]["motionEnergy"],
                                            "colour": sc["measured"]["mean"]}}
        if tr:
            entry["transition"] = implementation(tr)
            if entry["transition"]["type"] != "cut":
                entry["transition"]["duration"] = round(min(entry["transition"]["duration"] * k, entry["duration"] / 2), 2)
        scenes.append(entry)
    # Rounding must not change the runtime the reference sets.
    drift = round(runtime - sum(s["duration"] for s in scenes), 2)
    scenes[-1]["duration"] = round(scenes[-1]["duration"] + drift, 2)
    style = {"preset": cfg["style"]["preset"]}
    if ws.scan.exists():
        from .analyzer import brand_accent
        acc = brand_accent(read_json(ws.scan))
        if acc:
            style["accent"] = acc["value"]  # the product's colour, not the reference's
    tl = {"version": 1, "product": cfg["product"]["name"], "source": "reference", "seed": cfg["seed"],
          "style": style,
          "reference": {"breakdown": "reference/breakdown.json", "fingerprint": bd["fingerprint"],
                        "runtime": runtime, "scale": round(k, 4), "dropped": [], "deviations": []},
          "narration": {"enabled": True}, "scenes": scenes}
    write_json(ws.timeline, tl)
    return ws.timeline


def structure_check(tl: dict, bd: dict, cfg: dict) -> Report:
    """The film keeps the reference's structure: every measured scene is realised (or
    dropped with a reason), in order, at about its scaled length, entered by the measured
    transition. Anything else must be declared in a `deviation`."""
    r = Report()
    where = "timeline (reference structure)"
    ref_ids = [s["id"] for s in bd["scenes"]]
    meas = {s["id"]: s for s in bd["scenes"]}
    in_tr = {t["to"]: t for t in bd["transitions"]}
    ref_meta = tl.get("reference") or {}
    if ref_meta.get("fingerprint") and ref_meta["fingerprint"] != bd["fingerprint"]:
        r.error(where, "the timeline was derived from a different measurement of the reference; re-run `promo storyboard`")
    runtime = target_runtime(bd, cfg)
    k = runtime / bd["metadata"]["duration"]
    share = spans(bd)
    dropped = {d.get("ref"): d for d in ref_meta.get("dropped", []) if isinstance(d, dict)}
    for sid, d in dropped.items():
        if sid not in meas:
            r.error(where, f"dropped scene {sid} was not measured")
        elif not d.get("reason"):
            r.error(where, f"dropped scene {sid} needs a reason")
    covered, last_pos = set(), -1
    for s in tl.get("scenes", []):
        sid = s.get("id", "?")
        refs = s.get("ref")
        refs = [refs] if isinstance(refs, str) else list(refs or [])
        dev = s.get("deviation")
        if not refs:
            if not dev:
                r.error(where, f"scene '{sid}' has no `ref` to a reference scene and no `deviation` explaining it")
            continue
        unknown = [x for x in refs if x not in meas]
        if unknown:
            r.error(where, f"scene '{sid}' refers to unmeasured {', '.join(unknown)}")
            continue
        pos = [ref_ids.index(x) for x in refs]
        if pos != sorted(pos) or pos[0] <= last_pos and not dev:
            r.error(where, f"scene '{sid}' breaks the reference's order ({', '.join(refs)})")
        if pos != list(range(pos[0], pos[0] + len(pos))):
            r.error(where, f"scene '{sid}' merges non-adjacent reference scenes")
        last_pos = max(last_pos, pos[-1])
        covered.update(refs)
        want = sum(share[x] for x in refs) * k
        got = float(s.get("duration") or 0)
        if want and abs(got - want) > max(0.35, DURATION_TOLERANCE * want) and not dev:
            r.error(where, f"scene '{sid}' runs {got:.2f}s; the reference's {'+'.join(refs)} scaled is {want:.2f}s "
                    f"(±{int(DURATION_TOLERANCE * 100)}%). Match it or add a `deviation`")
        tr_in = in_tr.get(refs[0])
        if tr_in:
            want_tr = implementation(tr_in)
            got_tr = (s.get("transition") or {}).get("type", "fade")
            if got_tr != want_tr["type"] and not dev:
                r.error(where, f"scene '{sid}' enters by '{got_tr}' but the reference uses {tr_in['type']} "
                        f"({tr_in['id']} → '{want_tr['type']}'). Match it or add a `deviation`")
            if want_tr["type"] == "wipe" and got_tr == "wipe" and (s.get("transition") or {}).get("direction") != \
                    want_tr["direction"] and not dev:
                r.error(where, f"scene '{sid}' wipes {(s.get('transition') or {}).get('direction')}; "
                        f"the reference wipes {want_tr['direction']}")
    for sid in ref_ids:
        if sid not in covered and sid not in dropped:
            r.error(where, f"reference scene {sid} is neither realised nor dropped with a reason")
    total = sum(float(s.get("duration") or 0) for s in tl.get("scenes", []))
    if abs(total - runtime) > RUNTIME_TOLERANCE * runtime and not ref_meta.get("runtimeDeviation"):
        r.error(where, f"runtime {total:.1f}s is more than {int(RUNTIME_TOLERANCE * 100)}% from the reference's "
                f"{runtime:.1f}s; match it or set reference.runtimeDeviation with the reason")
    return r


# ── Mode A ─────────────────────────────────────────────────────────────────────────

def write_autonomous(ws: Workspace, rc: dict) -> Path:
    """CREATIVE_DIRECTION.md for Mode A, from the authored creative prompt and the compiled film."""
    creative = ws.creative.read_text() if ws.creative.exists() else ""
    body = re.sub(r"^# PRODUCT-SPECIFIC PROMO PROMPT\s*", "", creative).strip()
    fps = rc["fps"]
    L = [HEADER_A, "",
         "Creative source: the MASTER CREATIVE FRAMEWORK (no reference video). Product truth: product-brief.md.",
         f"Runtime {rc['duration']:.1f} s · {len(rc['scenes'])} scenes · audio: {rc.get('audioPolicy', {}).get('mode', 'voiceover')} "
         "· background music: never.", "", "## WHY EACH SCENE EXISTS", "",
         "| # | Time | Scene | Primitive | Why it is in the film | Built from | Claims |", "|---|---|---|---|---|---|---|"]
    for i, s in enumerate(rc["scenes"], 1):
        a, b = s["from"] / fps, (s["from"] + s["durationInFrames"]) / fps
        L.append(f"| {i} | {fmt_time(a)}–{fmt_time(b)} | {s['id']} | {s['kind']} | {s['purpose']} | "
                 f"{s.get('source') or '—'} | {', '.join(s['claims']) or '—'} |")
    L += ["", "## CREATIVE PROMPT", "", body or "(creative-prompt.md is missing)", ""]
    ws.direction.write_text("\n".join(L))
    return ws.direction


def is_reference_run(ws: Workspace) -> bool:
    return mode(ws.config()) == "reference"
