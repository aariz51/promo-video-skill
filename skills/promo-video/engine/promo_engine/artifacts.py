"""Layer 4 (and brief/creative contracts): the written artifacts and their validators.

The agent writes three Markdown artifacts. These functions hold them to their contracts
so a vague summary cannot pass for an analysis, an unsourced claim cannot reach the film,
and wording from an inspiration video cannot leak into the product's promo.
"""
from __future__ import annotations

import re
from pathlib import Path

from .util import Report

INSPIRATION_SECTIONS = [
    "1. VIDEO IDENTITY", "2. HOOK ANALYSIS", "3. STORY STRUCTURE", "4. PACING ANALYSIS",
    "5. MOTION LANGUAGE", "6. VISUAL LANGUAGE", "7. SOUND LANGUAGE", "8. NARRATION STRUCTURE",
    "9. TYPOGRAPHY SYSTEM", "10. SCENE TRANSITION SYSTEM", "11. CINEMATIC ARC",
    "12. REUSABLE CREATIVE RULES",
]
BRIEF_SECTIONS = [
    "PRODUCT", "TARGET USER", "CORE PROBLEM", "VALUE PROPOSITION", "HERO FEATURES",
    "PRODUCT MOMENTS", "VISUAL ASSETS", "DEMO OPPORTUNITIES", "FACTUAL CLAIMS", "RESTRICTIONS",
]
CREATIVE_SECTIONS = [
    "CORE MESSAGE", "CREATIVE DNA", "PACING PLAN", "SCENE PLAN", "MOTION & VISUAL SYSTEM",
    "SOUND DESIGN", "NARRATION", "ORIGINALITY", "FACT CHECK",
]

TIMESTAMP = re.compile(r"\b(\d{1,2}):(\d{2})(?:\.\d+)?\b")
_CLAIM = re.compile(r"^\s*[-*]\s*(C\d+)\s*[:.)-]\s*(.+?)\s*(?:[—–-]{1,2}\s*)?source\s*:\s*(.+?)\s*$", re.I)
_RULE = re.compile(r"^\s*(\d+)[.)]\s+(?:(R\d+)\s*[—–:-]\s*)?(.+)$")
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}|\bTODO\b")


def sections(md: str) -> dict[str, str]:
    """Map each `## Heading` to its body. Headings are normalised to upper case."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in md.splitlines():
        if line.startswith("## "):
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = line[3:].strip().upper()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def _strip_comments(md: str) -> str:
    return re.sub(r"<!--.*?-->", "", md, flags=re.S)


def _has_content(body: str) -> bool:
    """True when a section says something beyond empty template bullets or table headers."""
    for ln in body.splitlines():
        s = ln.strip()
        if not s or re.fullmatch(r"\|?[\s|:-]*\|?", s):
            continue
        if re.fullmatch(r"[-*]\s*[^:]{1,60}:\s*", s):  # "- Label:" with nothing after it
            continue
        if s.startswith("|") and all(not c.strip() for c in s.strip("|").split("|")[1:]):
            continue  # table row with only the first cell filled
        return True
    return False


def seconds(m: re.Match) -> int:
    return int(m.group(1)) * 60 + int(m.group(2))


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def copied_phrases(text: str, source_lines: list[str], n: int = 7) -> list[str]:
    """Runs of `n`+ consecutive words shared with the source transcript."""
    src = words(" ".join(source_lines))
    if len(src) < n:
        return []
    grams = {tuple(src[i:i + n]) for i in range(len(src) - n + 1)}
    tw = words(text)
    hits, i = [], 0
    while i <= len(tw) - n:
        if tuple(tw[i:i + n]) in grams:
            j = i + n
            while j < len(tw) and tuple(tw[j - n + 1:j + 1]) in grams:
                j += 1
            hits.append(" ".join(tw[i:j]))
            i = j
        else:
            i += 1
    return hits


def check_inspiration(md: str, evidence: dict | None = None) -> Report:
    r = Report()
    where = "inspiration-analysis.md"
    if not md.lstrip().startswith("# YOUTUBE INSPIRATIONAL PROMPT"):
        r.error(where, "must start with '# YOUTUBE INSPIRATIONAL PROMPT'")
    body = _strip_comments(md)
    secs = sections(body)
    keys = list(secs)
    for want in INSPIRATION_SECTIONS:
        if want not in secs:
            r.error(where, f"missing section '## {want}'")
        elif not _has_content(secs[want]):
            r.error(where, f"section '{want}' is empty")
    present = [k for k in keys if k in INSPIRATION_SECTIONS]
    if present != [s for s in INSPIRATION_SECTIONS if s in present]:
        r.error(where, "sections are out of order")
    if PLACEHOLDER.search(body):
        r.error(where, "unfilled placeholders ({{…}} or TODO) remain")

    story = secs.get("3. STORY STRUCTURE", "")
    rows = [ln for ln in story.splitlines() if ln.strip().startswith("|") and TIMESTAMP.search(ln)]
    if len(rows) < 3:
        r.error(where, "STORY STRUCTURE needs at least 3 timestamped scene rows")
    hook = secs.get("2. HOOK ANALYSIS", "")
    if hook and not TIMESTAMP.search(hook):
        r.error(where, "HOOK ANALYSIS must cite timestamps")
    arc = secs.get("11. CINEMATIC ARC", "")
    if arc and not TIMESTAMP.search(arc):
        r.error(where, "CINEMATIC ARC must cite timestamps from the video")

    rules = [m for m in (_RULE.match(ln) for ln in secs.get("12. REUSABLE CREATIVE RULES", "").splitlines()) if m]
    if not 10 <= len(rules) <= 20:
        r.error(where, f"REUSABLE CREATIVE RULES needs 10–20 numbered rules (found {len(rules)})")
    unevidenced = [m.group(1) for m in rules if not TIMESTAMP.search(m.group(3))]
    if unevidenced:
        r.warn(where, f"rules without a timestamp as evidence: {', '.join(unevidenced)}")

    if evidence:
        dur = float(evidence.get("duration") or 0)
        if dur:
            late = sorted({m.group(0) for m in TIMESTAMP.finditer(body) if seconds(m) > dur + 1})
            if late:
                r.error(where, f"timestamps beyond the video's {dur:.0f}s length: {', '.join(late[:6])}")
        lines = [l["text"] for l in (evidence.get("transcript") or {}).get("lines", [])]
        copied = copied_phrases(body, lines)
        if copied:
            r.error(where, "copies narration verbatim (describe its structure instead): "
                    + "; ".join(f"“{c}”" for c in copied[:3]))
        if not (evidence.get("transcript") or {}).get("available"):
            narr = secs.get("8. NARRATION STRUCTURE", "").lower()
            if "not observable" not in narr and "no transcript" not in narr and "no narration" not in narr:
                r.warn(where, "no transcript was available; say so in NARRATION STRUCTURE rather than infer")
    return r


def parse_rules(md: str) -> list[dict]:
    body = sections(_strip_comments(md)).get("12. REUSABLE CREATIVE RULES", "")
    out = []
    for ln in body.splitlines():
        m = _RULE.match(ln)
        if m:
            out.append({"id": m.group(2) or f"R{m.group(1)}", "text": m.group(3).strip()})
    return out


def parse_claims(md: str) -> dict[str, dict]:
    body = sections(_strip_comments(md)).get("FACTUAL CLAIMS", "")
    claims: dict[str, dict] = {}
    for ln in body.splitlines():
        m = _CLAIM.match(ln)
        if m:
            cid = m.group(1).upper()
            claims.setdefault(cid, {"text": m.group(2).strip().rstrip("—–- "), "source": m.group(3).strip(),
                                    "duplicate": False})
            if claims[cid]["text"] != m.group(2).strip().rstrip("—–- "):
                claims[cid]["duplicate"] = True
    return claims


def _source_paths(source: str) -> list[tuple[str, int | None]]:
    out = []
    for part in re.split(r"[;,]\s*", source):
        part = part.strip().strip("`")
        if not part or part.startswith(("http://", "https://", "supplied:", "user:")):
            continue
        m = re.match(r"^(.+?)(?::(\d+)(?:-\d+)?)?$", part)
        if m:
            out.append((m.group(1), int(m.group(2)) if m.group(2) else None))
    return out


def check_brief(md: str, product_root: str | Path) -> Report:
    r = Report()
    where = "product-brief.md"
    root = Path(product_root)
    if not md.lstrip().startswith("# PRODUCT PROMO BRIEF"):
        r.error(where, "must start with '# PRODUCT PROMO BRIEF'")
    body = _strip_comments(md)
    secs = sections(body)
    for want in BRIEF_SECTIONS:
        if want not in secs:
            r.error(where, f"missing section '## {want}'")
        elif not _has_content(secs[want]):
            r.error(where, f"section '{want}' is empty")
    if PLACEHOLDER.search(body):
        r.error(where, "unfilled placeholders ({{…}} or TODO) remain")
    claims = parse_claims(md)
    if len(claims) < 3:
        r.error(where, f"FACTUAL CLAIMS needs at least 3 sourced claims as '- C1: … — source: path' (found {len(claims)})")
    for cid, c in claims.items():
        if c["duplicate"]:
            r.error(where, f"claim id {cid} is used twice with different text")
        paths = _source_paths(c["source"])
        if not paths and not c["source"].startswith(("http", "supplied:", "user:")):
            r.error(where, f"{cid} has no usable source")
        for rel, line in paths:
            p = (root / rel).resolve()
            if not p.exists():
                r.error(where, f"{cid} cites '{rel}', which does not exist in the product")
            elif line and p.is_file():
                with p.open(errors="replace") as fh:
                    n = sum(1 for _ in fh)
                if line > n:
                    r.error(where, f"{cid} cites line {line} of '{rel}', which has {n} lines")
    return r


def check_creative(md: str, *, claims: dict[str, dict], source: str, rules: list[dict] | None = None,
                   transcript: list[str] | None = None) -> Report:
    r = Report()
    where = "creative-prompt.md"
    if not md.lstrip().startswith("# PRODUCT-SPECIFIC PROMO PROMPT"):
        r.error(where, "must start with '# PRODUCT-SPECIFIC PROMO PROMPT'")
    body = _strip_comments(md)
    secs = sections(body)
    for want in CREATIVE_SECTIONS:
        if want not in secs:
            r.error(where, f"missing section '## {want}'")
        elif not _has_content(secs[want]):
            r.error(where, f"section '{want}' is empty")
    if PLACEHOLDER.search(body):
        r.error(where, "unfilled placeholders ({{…}} or TODO) remain")
    scene_rows = [ln for ln in secs.get("SCENE PLAN", "").splitlines()
                  if ln.strip().startswith("|") and not re.fullmatch(r"\|[\s|:-]*\|", ln.strip())][1:]
    if len(scene_rows) < 5:
        r.error(where, f"SCENE PLAN needs at least 5 scenes (found {len(scene_rows)})")
    cited = set(re.findall(r"\bC\d+\b", body))
    unknown = sorted(cited - set(claims), key=lambda c: int(c[1:]))
    if unknown:
        r.error(where, f"references claims not in the brief: {', '.join(unknown)}")
    dna = secs.get("CREATIVE DNA", "")
    if source == "inspiration":
        rule_ids = {x["id"] for x in rules or []}
        used = set(re.findall(r"\bR\d+\b", dna)) & rule_ids
        if rules and len(used) < min(5, len(rule_ids)):
            r.error(where, f"CREATIVE DNA must carry the inspiration's rules forward (cites {len(used)} of {len(rule_ids)})")
    else:
        if len(re.findall(r"§\s*\d+|framework", dna, re.I)) < 3:
            r.error(where, "CREATIVE DNA must cite the master framework sections it applies (e.g. §4, §6)")
    if re.search(r"background music|music bed|soundtrack", body, re.I) and not re.search(
            r"no (background )?music|without (background )?music|music[^.\n]{0,40}(is |are )?(not used|excluded|absent)",
            body, re.I):
        r.error(where, "mentions music without excluding it; background music is never used")
    if transcript:
        copied = copied_phrases(body, transcript)
        if copied:
            r.error(where, "reuses inspiration narration verbatim: " + "; ".join(f"“{c}”" for c in copied[:3]))
    return r
