"""Layer 5: CREATIVE ADAPTER.

    creative structure (MASTER CREATIVE FRAMEWORK or YOUTUBE INSPIRATIONAL PROMPT)
  + product truth      (PRODUCT PROMO BRIEF)
  = PRODUCT-SPECIFIC PROMO PROMPT

`scaffold()` does the deterministic half of the transformation: it carries the source's
rules into CREATIVE DNA, rescales the source's scene structure and pacing to the target
runtime, and lays out one SCENE PLAN row per source beat with the product columns left as
TODO. The agent fills those cells from the brief (the creative half), and
`artifacts.check_creative` refuses the file until every TODO is gone.
"""
from __future__ import annotations

import re
from pathlib import Path

from .artifacts import TIMESTAMP, parse_claims, parse_rules, sections, _strip_comments
from .config import Workspace, mode, reference_source
from .util import FRAMEWORK_DIR, PromoError, read_json

_RANGE = re.compile(r"(\d{1,2}):(\d{2}(?:\.\d+)?)\s*[–—-]\s*(\d{1,2}):(\d{2}(?:\.\d+)?)")


def target_runtime(source_duration: float | None, lo: float, hi: float) -> float:
    """Keep the source's length when it fits the configured range; otherwise clamp."""
    if not source_duration:
        return round((lo + hi) / 2)
    return float(round(min(max(source_duration, lo), hi)))


def framework_beats(md: str | None = None) -> list[dict]:
    """The arc table from §4 of the master framework."""
    md = md or (FRAMEWORK_DIR / "master-creative-framework.md").read_text()
    beats = []
    for ln in md.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[0].isdigit():
            lo_hi = re.findall(r"\d+", cells[3])
            nums = [int(x) for x in lo_hi[:2]] or [6]
            length = sum(nums) / len(nums)
            beats.append({"n": int(cells[0]), "beat": cells[1].strip("*"), "job": cells[2],
                          "length": length, "keep": cells[4]})
    if not beats:
        raise PromoError("could not read the arc table from the master creative framework")
    return beats


def inspiration_scenes(md: str) -> list[dict]:
    """Scene rows (start, end, purpose) from STORY STRUCTURE of the inspiration prompt."""
    story = sections(_strip_comments(md)).get("3. STORY STRUCTURE", "")
    rows = []
    for ln in story.splitlines():
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        m = _RANGE.search(cells[0]) if cells else None
        if not m:
            continue
        a = int(m.group(1)) * 60 + float(m.group(2))
        b = int(m.group(3)) * 60 + float(m.group(4))
        rows.append({"start": a, "end": b, "purpose": cells[1] if len(cells) > 1 else "",
                     "transition": cells[9] if len(cells) > 9 else "",
                     "sound": cells[10] if len(cells) > 10 else ""})
    return rows


def _fmt(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    return f"{int(m)}:{s:04.1f}"


def scaffold(ws: Workspace, *, force: bool = False) -> Path:
    if ws.creative.exists() and not force:
        raise PromoError(f"{ws.creative.name} already exists", hint="edit it, or pass --force to regenerate the scaffold")
    if not ws.brief.exists():
        raise PromoError("write product-brief.md first (the adapter needs product truth)")
    cfg = ws.config()
    claims = parse_claims(ws.brief.read_text())
    name = cfg["product"]["name"] or "the product"
    lo, hi = cfg["duration"]["min"], cfg["duration"]["max"]
    use_reference = mode(cfg) == "reference" and ws.direction.exists()
    use_inspiration = not use_reference and ws.inspiration.exists() and mode(cfg) == "reference"
    if mode(cfg) == "reference" and not (use_reference or use_inspiration):
        raise PromoError("write CREATIVE_DIRECTION.md first (`promo direction`), so the prompt follows the reference")

    lines = ["# PRODUCT-SPECIFIC PROMO PROMPT", ""]
    if use_reference:
        from . import direction
        bd = direction.load_breakdown(ws)
        runtime = direction.target_runtime(bd, cfg)
        k = runtime / bd["metadata"]["duration"]
        rules = direction.parse_rules(ws.direction.read_text())
        ms = bd["motionSpec"]
        lines += [f"Source of creative structure: CREATIVE_DIRECTION.md (reference {reference_source(cfg)}, measured)",
                  f"Product: {name}",
                  f"Target runtime: {runtime:.1f} s (reference {bd['metadata']['duration']:.1f} s, ×{k:.2f})",
                  "", "## CORE MESSAGE", "", "TODO: one sentence, then the three carrying ideas, from the brief.",
                  "", "## CREATIVE DNA", ""]
        lines += [f"- {r['id']} — {r['text']}  → for {name}: TODO" for r in rules]
        lines += ["", "## PACING PLAN", "",
                  f"Reference: {ms['sceneCount']} scenes, average {ms['averageScene']} s, "
                  f"{ms['boundariesPerMinute']} boundaries/min, hard cuts {ms['hardCutShare']}. "
                  "The timeline keeps this structure (`promo storyboard`).", ""]
        lines += [f"- {_fmt(q['from'] * k)}–{_fmt(q['to'] * k)}: {q['perMinute']} boundaries/min in the reference"
                  for q in ms["byQuarter"]]
        lines += ["- TODO: where the product's hero moment and the holds land in this rhythm.", "",
                  "## SCENE PLAN", "",
                  "| # | Time | Beat (source) | Product scene | Primitive | Evidence (claim ids) | Transition in | Sound | Narration |",
                  "|---|---|---|---|---|---|---|---|---|"]
        t = 0.0
        share = direction.spans(bd)
        in_tr = {x["to"]: x for x in bd["transitions"]}
        for i, sc in enumerate(bd["scenes"], 1):
            d = share[sc["id"]] * k
            tr = in_tr.get(sc["id"])
            tr_s = direction.implementation(tr)["type"] + f" (ref {tr['type']})" if tr else "—"
            lines.append(f"| {i} | {_fmt(t)}–{_fmt(t + d)} | {sc['id']}: {sc['measured']['camera']} "
                         f"| TODO | TODO | TODO | {tr_s} | TODO | TODO |")
            t += d
    elif use_inspiration:
        md = ws.inspiration.read_text()
        ev = read_json(ws.evidence) if ws.evidence.exists() else {}
        src_dur = float(ev.get("duration") or 0)
        rows = inspiration_scenes(md)
        if not rows:
            raise PromoError("inspiration-analysis.md has no timestamped STORY STRUCTURE rows to adapt")
        src_dur = src_dur or rows[-1]["end"]
        runtime = target_runtime(src_dur, lo, hi)
        k = runtime / src_dur
        rules = parse_rules(md)
        lines += [f"Source of creative structure: YOUTUBE INSPIRATIONAL PROMPT ({reference_source(cfg)})",
                  f"Product: {name}",
                  f"Target runtime: {runtime:.0f} s (source {src_dur:.1f} s, time scale ×{k:.2f}) · Master: 1920×1080 16:9 · Adaptations: 9:16, 1:1",
                  "", "## CORE MESSAGE", "", "TODO: one sentence, then the three carrying ideas, from the brief.",
                  "", "## CREATIVE DNA", ""]
        lines += [f"- {r['id']} — {r['text']}  → for {name}: TODO" for r in rules]
        pacing = ev.get("pacing") or {}
        lines += ["", "## PACING PLAN", "",
                  f"Source averages {pacing.get('averageShot', '?')} s per shot over {pacing.get('cutCount', '?')} cuts; "
                  f"scaled ×{k:.2f} that is ~{(pacing.get('averageShot') or 0) * k:.1f} s per shot.", ""]
        for q in pacing.get("quarters", []):
            lines.append(f"- {_fmt(q['from'] * k)}–{_fmt(q['to'] * k)}: {q['cutsPerMinute']} cuts/min in the source")
        lines += ["- TODO: holds, the acceleration section and the still ending, in seconds.", "",
                  "## SCENE PLAN", "",
                  "| # | Time | Beat (source) | Product scene | Primitive | Evidence (claim ids) | Transition in | Sound | Narration |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for i, row in enumerate(rows, 1):
            lines.append(f"| {i} | {_fmt(row['start'] * k)}–{_fmt(row['end'] * k)} | {_fmt(row['start'])} {row['purpose']} "
                         f"| TODO | TODO | TODO | {row['transition'] or 'TODO'} | TODO | TODO |")
    else:
        beats = framework_beats()
        runtime = target_runtime(None, lo, hi)
        lines += ["Source of creative structure: MASTER CREATIVE FRAMEWORK (framework/master-creative-framework.md)",
                  f"Product: {name}",
                  f"Target runtime: {runtime:.0f} s · Master: 1920×1080 16:9 · Adaptations: 9:16, 1:1",
                  "", "## CORE MESSAGE", "", "TODO: one sentence, then the three carrying ideas, from the brief.",
                  "", "## CREATIVE DNA", "",
                  f"- §4 arc: mystery before name, name before structure, proof before breadth → for {name}: TODO",
                  f"- §5 pacing: 5–8 s beats, holds after reveals, one acceleration, still ending → for {name}: TODO",
                  f"- §6 show, don't tell: input → process → result → for {name}: TODO",
                  f"- §7–9 visual, motion, typography: one ground per act, one accent, rare large type → for {name}: TODO",
                  f"- §10–11 sound and narration: no background music, sparse lines → for {name}: TODO",
                  f"- §12 factual accuracy: only claims C1…C{len(claims)} from the brief → for {name}: TODO",
                  "", "## PACING PLAN", "", "TODO: beat lengths, holds, acceleration, still ending, in seconds.", "",
                  "## SCENE PLAN", "",
                  "Delete beats the product cannot support truthfully (see “Keep when”) and give their time to "
                  "the beats that remain. Times are scaled to the target runtime.", "",
                  "| # | Time | Beat (source) | Product scene | Primitive | Evidence (claim ids) | Transition in | Sound | Narration |",
                  "|---|---|---|---|---|---|---|---|---|"]
        # Default beat lengths fill ~94 s; scale them to the chosen runtime. Beats the product
        # cannot support are deleted and their time given to the rest.
        k = runtime / sum(b["length"] for b in beats)
        t = 0.0
        for b in beats:
            d = b["length"] * k
            lines.append(f"| {b['n']} | {_fmt(t)}–{_fmt(t + d)} | §4 {b['beat']} (keep when: {b['keep']}) "
                         f"| TODO | TODO | TODO | TODO | TODO | TODO |")
            t += d
    lines += ["", "## MOTION & VISUAL SYSTEM", "", "TODO: ground, accent, type, depth, camera grammar, transitions.",
              "", "## SOUND DESIGN", "", "No background music. TODO: layers and where they fire.",
              "", "## NARRATION", "", "TODO: one sparse line per beat, and one sentence of voice direction.",
              "", "## ORIGINALITY", "",
              ("Structure, pacing and technique are taken from the reference; subject, visuals, UI, claims and "
               "words are the product's own. TODO: list what was kept and what was replaced."
               if use_inspiration or use_reference else
               "The film is built from the master framework and the product's own material. TODO: confirm."),
              "", "## FACT CHECK", ""]
    lines += [f"- {cid}: {c['text']} — {c['source']}" for cid, c in sorted(claims.items(), key=lambda x: int(x[0][1:]))]
    ws.creative.write_text("\n".join(lines) + "\n")
    return ws.creative
