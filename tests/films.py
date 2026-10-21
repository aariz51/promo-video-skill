"""Short, real films for the render tests: small enough to render in seconds, complete
enough to exercise every transition the reference analysis can ask for."""
from __future__ import annotations

COMPACT = {
    "version": 1, "product": "Tallyboard", "source": "framework", "seed": 3,
    "style": {"preset": "graphite", "accent": "#1F8A70"},
    "narration": {"enabled": True},
    "scenes": [
        {"id": "open", "kind": "statement", "duration": 2.5, "purpose": "the question before the name",
         "props": {"text": "Where did this month go?", "eyebrow": "Every receipt, somewhere"},
         "narration": {"text": "Every month ends the same way.", "offset": 0.3}},
        {"id": "title", "kind": "title", "duration": 2.5, "purpose": "the name lands",
         "transition": {"type": "fade", "duration": 0.5},
         "props": {"name": "Tallyboard", "tagline": "Receipts in. A finished report out."}},
        {"id": "screen", "kind": "screen", "duration": 3.5, "purpose": "the real report view", "claims": ["C2"],
         "transition": {"type": "push", "duration": 0.5, "direction": "left"},
         "props": {"media": "screenshots/dashboard.png", "device": "browser", "camera": "push",
                   "callouts": [{"x": 0.3, "y": 0.4, "label": "Export CSV"}]},
         "narration": "The month exports as a spreadsheet."},
        {"id": "flow", "kind": "flow", "duration": 3.5, "purpose": "receipts to report", "claims": ["C1"],
         "transition": {"type": "wipe", "duration": 0.6, "direction": "right"},
         "props": {"title": "From receipts to a report", "steps": [
             {"label": "Drop receipts"}, {"label": "Grouped by category"}, {"label": "Monthly report"}]}},
        {"id": "lockup", "kind": "lockup", "duration": 3.5, "purpose": "close on the name",
         "transition": {"type": "dip", "duration": 0.8, "color": "black"},
         "props": {"name": "Tallyboard", "line": "Drop. Group. Export."},
         "narration": "Tallyboard. The month, sorted."},
    ],
}


def complete_creative_prompt(scaffold: str) -> str:
    """Stand in for the agent's creative half of `promo adapt`: every TODO answered from the
    fixture brief (Tallyboard), keeping the framework citations the scaffold carries."""
    out = scaffold.replace(
        "TODO: one sentence, then the three carrying ideas, from the brief.",
        "Receipts in, a finished monthly report out. Ideas: drop · group · export.")
    out = out.replace("TODO: beat lengths, holds, acceleration, still ending, in seconds.",
                      "2.5 s question, 2.5 s name, 3.5 s proof, 3.5 s demonstration, 3.5 s still ending.")
    out = out.replace("TODO: ground, accent, type, depth, camera grammar, transitions.",
                      "Graphite ground, brand green #1F8A70, one sans; push on the proof, wipe into the demo, dip to close.")
    out = out.replace("No background music. TODO: layers and where they fire.",
                      "No background music. Clicks on interaction, a chime when the report resolves.")
    out = out.replace("TODO: one sparse line per beat, and one sentence of voice direction.",
                      "Three short lines; calm and precise.")
    out = out.replace("The film is built from the master framework and the product's own material. TODO: confirm.",
                      "The film is built from the master framework and the product's own material.")
    out = out.replace("→ for Tallyboard: TODO", "→ for Tallyboard: applied in the compact cut (C1, C2)")
    while "| TODO |" in out:  # adjacent cells share a pipe, so one pass only fills every other one
        out = out.replace("| TODO |", "| C1 |")
    return out
