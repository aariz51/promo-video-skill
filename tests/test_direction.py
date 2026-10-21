"""CREATIVE_DIRECTION.md, the reference-derived storyboard, and structural fidelity."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
from helpers import Env, has_ffmpeg  # noqa: E402

from promo_engine import adapter, artifacts, direction, reference, timeline
from promo_engine.cli import main
from promo_engine.util import PromoError, read_json, write_json

_TMP = Path(tempfile.mkdtemp(prefix="promo-dir-"))
_VIDEOS: dict[str, Path] = {}


def reference_video(profile: str) -> Path:
    if profile not in _VIDEOS:
        _VIDEOS[profile] = _TMP / f"{profile}.mp4"
        helpers.make_reference(_VIDEOS[profile], profile)
    return _VIDEOS[profile]


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def reference_env(profile: str) -> Env:
    """A workspace in Mode B with the profile's reference measured."""
    from promo_engine import analyzer
    env = Env()
    video = reference_video(profile)
    assert main(["-w", str(env.ws.root), "init", "--product", str(env.product), "--reference", str(video),
                 "--audio", "effects", "--formats", "16:9"]) == 0
    reference.analyze(video, env.ws.reference_dir, source=str(video))
    env.ws.brief.write_text(helpers.BRIEF)
    write_json(env.ws.scan, analyzer.scan(env.product, exclude=env.ws.root))
    helpers.discover_offline(env.ws)
    return env


def fill_direction(md: str, bd: dict) -> str:
    """What the agent does after reading the frames: every TODO becomes an observation."""
    md = md.replace("TODO", "Observed: a flat colour field, no type; Interpretation: a held beat")
    ids = [s["id"] for s in bd["scenes"]] + [t["id"] for t in bd["transitions"]]
    rules = "\n".join(f"{i}. Hold each beat about as long as {ids[i % len(ids)]} does before the next change."
                      for i in range(1, 11))
    return re.sub(r"^1\. Observed:.*$", rules, md, count=1, flags=re.M)


BEATS = [("statement", {"text": "Where did this month go?", "eyebrow": "Every receipt, somewhere"}),
         ("title", {"name": "Tallyboard", "tagline": "Receipts in. A finished report out."}),
         ("compare", {"left": {"title": "By hand", "items": ["Sort receipts", "Type totals"]},
                      "right": {"title": "Tallyboard", "items": ["Grouped by category", "Export CSV"]}}),
         ("pillars", {"items": [{"title": "Drop"}, {"title": "Group"}, {"title": "Export"}]}),
         ("statement", {"text": "Your receipts never leave your machine.", "eyebrow": "Local by design"})]


def fill_timeline(tl: dict) -> dict:
    """Give every skeleton scene a real, distinct primitive and purpose; keep the structure."""
    for i, s in enumerate(tl["scenes"]):
        kind, props = ("lockup", {"name": "Tallyboard", "line": "Drop. Group. Export."}) \
            if i == len(tl["scenes"]) - 1 else BEATS[i % len(BEATS)]
        s["kind"], s["props"] = kind, json.loads(json.dumps(props))
        if s.get("suggest") and i < len(tl["scenes"]) - 1:  # the storyboard proposed a real screen here
            s["kind"], s["props"] = "screen", {"media": s["suggest"]["media"], "device": "browser", "camera": "push"}
        s["purpose"] = f"beat {i + 1}, following reference {s['ref']}"
        if kind == "compare":
            s["claims"] = ["C1", "C2"]
    return tl


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class DirectionDocument(unittest.TestCase):
    def setUp(self):
        self.env = reference_env("slow")
        self.bd = direction.load_breakdown(self.env.ws)

    def tearDown(self):
        self.env.close()

    def test_scaffold_has_every_scene_field_and_transition(self):
        self.assertEqual(main(["-w", str(self.env.ws.root), "direction"]), 0)
        md = self.env.ws.direction.read_text()
        self.assertTrue(md.startswith(direction.HEADER_B))
        for sc in self.bd["scenes"]:
            block = direction._scene_blocks(md)[sc["id"]]
            fields = [row[1] for row in direction._table_rows(block)]
            self.assertEqual(fields, direction.FIELDS, sc["id"])
            self.assertIn(f"measured: {sc['measured']['camera']}", block)
        for tr in self.bd["transitions"]:
            self.assertRegex(md, rf"\| {tr['id']} \| {tr['from']} → {tr['to']} \|")
        self.assertIn("| T02 | S02 → S03 | 0:04.8 | 0:05.4 | measured: wipe-left", md)
        self.assertIn("wipe duration=0.6 direction=left sweep=False easing=linear", md)
        self.assertIn("dip duration=0.8 color=black", md)
        rep = direction.check(md, self.bd, self.env.ws.root)
        self.assertFalse(rep.ok, "an unfilled scaffold must not pass")
        self.assertIn("is not filled in", rep.summary())

    def test_a_completed_direction_passes_and_each_defect_is_named(self):
        direction.scaffold(self.env.ws)
        good = fill_direction(self.env.ws.direction.read_text(), self.bd)
        rep = direction.check(good, self.bd, self.env.ws.root)
        self.assertTrue(rep.ok, rep.summary())
        defects = {
            "no breakdown for measured scene S03": lambda m: re.sub(r"### S03.*?(?=### S04)", "", m, flags=re.S),
            "does not exist": lambda m: m.replace("reference/frames/S01-mid", "reference/frames/S01-gone", 1),
            "is not a renderer transition": lambda m: m.replace("| wipe duration=0.6 direction=left sweep=False easing=linear |", "| morph |"),
            "which was not measured": lambda m: m.replace("as long as S02 does", "as long as S09 does", 1),
            "missing from TRANSITIONS": lambda m: re.sub(r"^\| T03 \|.*$\n", "", m, flags=re.M),
            "repeats the measurement without an observation":
                lambda m: re.sub(r"(\| 10 \| Camera movement \| measured: static hold) · [^|]*\|", r"\1 |", m, count=1),
            "REUSABLE RULES needs 10–20": lambda m: re.sub(r"^10\. .*$\n", "", m, flags=re.M),
            "mentions music without excluding it": lambda m: m + "\nA soft music bed carries the film.\n",
        }
        for needle, corrupt in defects.items():
            bad = corrupt(good)
            self.assertTrue(bad != good, f"the '{needle}' corruption did not change the document")
            self.assertIn(needle, direction.check(bad, self.bd, self.env.ws.root).summary(), needle)

    def test_direction_is_never_written_for_an_autonomous_run(self):
        main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product), "--reference", "none"])
        self.assertEqual(main(["-w", str(self.env.ws.root), "direction"]), 1)


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class ReferenceStoryboard(unittest.TestCase):
    def setUp(self):
        self.envs = {p: reference_env(p) for p in ("rapid", "slow")}

    def tearDown(self):
        for e in self.envs.values():
            e.close()

    def _skeleton(self, profile: str) -> dict:
        env = self.envs[profile]
        self.assertEqual(main(["-w", str(env.ws.root), "storyboard"]), 0)
        return read_json(env.ws.timeline)

    def test_skeleton_follows_the_reference(self):
        tl = self._skeleton("slow")
        bd = direction.load_breakdown(self.envs["slow"].ws)
        self.assertEqual([s["ref"] for s in tl["scenes"]], [s["id"] for s in bd["scenes"]])
        self.assertEqual([s.get("transition") for s in tl["scenes"]],
                         [None, {"type": "fade", "duration": 0.6, "easing": "linear"},
                          {"type": "wipe", "duration": 0.6, "direction": "left", "sweep": False, "easing": "linear"},
                          {"type": "dip", "duration": 0.8, "color": "black"}])  # easing measured: xfade is linear
        self.assertAlmostEqual(sum(s["duration"] for s in tl["scenes"]), bd["metadata"]["duration"], delta=0.02)
        # Each scene starts where the reference's transition into it starts, so the film's
        # transitions play at the reference's times (the renderer runs them over the incoming scene).
        starts = [round(sum(s["duration"] for s in tl["scenes"][:k]), 2) for k in range(1, len(tl["scenes"]))]
        self.assertEqual(starts, [t["start"] for t in bd["transitions"]])
        self.assertEqual(tl["source"], "reference")
        # The product's colour, measured from its code, not the reference's palette.
        self.assertEqual(tl["style"]["accent"], "#1F8A70")

    def test_two_references_give_materially_different_films(self):
        rapid, slow = self._skeleton("rapid"), self._skeleton("slow")
        shape = lambda tl: ([round(s["duration"], 1) for s in tl["scenes"]],  # noqa: E731
                            [(s.get("transition") or {}).get("type") for s in tl["scenes"][1:]])
        self.assertNotEqual(len(rapid["scenes"]), len(slow["scenes"]))
        self.assertEqual(shape(rapid)[1], ["cut"] * 4)
        self.assertEqual(shape(slow)[1], ["fade", "wipe", "dip"])
        self.assertLess(max(shape(rapid)[0]), min(shape(slow)[0]), "rapid's longest beat is shorter than slow's shortest")
        self.assertIn("pan", rapid["scenes"][3]["refMotion"]["camera"])
        # …and the finished timelines compile into different films.
        for profile in ("rapid", "slow"):
            env = self.envs[profile]
            write_json(env.ws.timeline, fill_timeline(read_json(env.ws.timeline)))
        rcs = {p: timeline.compile_timeline(e.ws) for p, e in self.envs.items()}
        for p, (rc, rep) in rcs.items():
            self.assertTrue(rep.ok, f"{p}: {rep.summary()}")
        a, b = rcs["rapid"][0], rcs["slow"][0]
        self.assertNotEqual([s["durationInFrames"] for s in a["scenes"]], [s["durationInFrames"] for s in b["scenes"]])
        self.assertNotEqual([s["transition"]["type"] for s in a["scenes"]], [s["transition"]["type"] for s in b["scenes"]])
        self.assertEqual(b["scenes"][2]["transition"],
                         {"type": "wipe", "frames": 18, "direction": "left", "sweep": False, "easing": "linear"})
        self.assertEqual(b["scenes"][3]["transition"], {"type": "dip", "frames": 24, "color": "black"})

    def test_structure_is_enforced_unless_a_deviation_is_declared(self):
        env = self.envs["slow"]
        tl = fill_timeline(self._skeleton("slow"))
        bd = direction.load_breakdown(env.ws)
        cfg = env.ws.config()
        self.assertTrue(direction.structure_check(tl, bd, cfg).ok)

        def errs(mutate) -> str:
            t = json.loads(json.dumps(tl))
            mutate(t)
            return direction.structure_check(t, bd, cfg).summary()

        self.assertIn("enters by 'fade' but the reference uses wipe-left",
                      errs(lambda t: t["scenes"][2].update(transition={"type": "fade", "duration": 0.6})))
        self.assertIn("wipes right; the reference wipes left",
                      errs(lambda t: t["scenes"][2]["transition"].update(direction="right")))
        self.assertIn("neither realised nor dropped", errs(lambda t: t["scenes"].pop(1)))
        self.assertIn("runs 6.00s", errs(lambda t: t["scenes"][1].update(duration=6.0)))
        self.assertIn("breaks the reference's order", errs(lambda t: t["scenes"].insert(0, t["scenes"].pop(2))))
        self.assertIn("no `ref`", errs(lambda t: t["scenes"].insert(1, {"id": "extra", "duration": 1})))
        # Declared departures are accepted, and recorded in the storyboard.
        ok = json.loads(json.dumps(tl))
        ok["scenes"][1].update(duration=4.0, deviation="the product's hero demo needs a longer hold")
        dropped = ok["scenes"].pop(2)
        ok["reference"]["dropped"] = [{"ref": dropped["ref"], "reason": "no product feature fits a third colour beat"}]
        ok["scenes"][-1]["duration"] += 0.4
        self.assertTrue(direction.structure_check(ok, bd, cfg).ok, direction.structure_check(ok, bd, cfg).summary())
        ok["reference"]["dropped"][0]["reason"] = ""
        self.assertIn("needs a reason", direction.structure_check(ok, bd, cfg).summary())

    def test_timeline_check_runs_the_structure_check_in_mode_b(self):
        env = self.envs["rapid"]
        tl = fill_timeline(self._skeleton("rapid"))
        tl["scenes"][2]["transition"] = {"type": "fade", "duration": 0.3}
        write_json(env.ws.timeline, tl)
        rep = timeline.validate(tl, env.ws, env.ws.config(), artifacts.parse_claims(helpers.BRIEF))
        self.assertIn("reference uses cut", rep.summary())
        tl["source"] = "framework"
        self.assertIn("source must be 'reference'", timeline.validate(tl, env.ws, env.ws.config(), {}).summary())


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class CreativePromptFromReference(unittest.TestCase):
    def test_adapter_uses_the_measured_scenes_and_the_direction_rules(self):
        env = reference_env("rapid")
        try:
            with self.assertRaises(PromoError):
                adapter.scaffold(env.ws)  # no direction yet: the prompt cannot follow the reference
            direction.scaffold(env.ws)
            env.ws.direction.write_text(fill_direction(env.ws.direction.read_text(), direction.load_breakdown(env.ws)))
            path = adapter.scaffold(env.ws)
            md = path.read_text()
            self.assertIn("Source of creative structure: CREATIVE_DIRECTION.md", md)
            plan = artifacts.sections(md)["SCENE PLAN"]
            self.assertEqual(len([ln for ln in plan.splitlines() if re.match(r"\| \d+ \|", ln)]), 5)
            self.assertIn("pan: content moves left", plan)
            self.assertEqual(len(re.findall(r"^- R\d+ — ", artifacts.sections(md)["CREATIVE DNA"], re.M)), 10)
        finally:
            env.close()


class AutonomousDirection(unittest.TestCase):
    def test_compile_writes_creative_direction_in_mode_a(self):
        env = Env().with_artifacts()
        try:
            main(["-w", str(env.ws.root), "init", "--product", str(env.product), "--reference", "none"])
            env.ws.creative.write_text("# PRODUCT-SPECIFIC PROMO PROMPT\n\n## CORE MESSAGE\n\nReceipts in, report out.\n")
            rc, rep = timeline.compile_timeline(env.ws)
            self.assertTrue(rep.ok, rep.summary())
            md = env.ws.direction.read_text()
            self.assertTrue(md.startswith(direction.HEADER_A))
            rows = [ln for ln in artifacts.sections(md)["WHY EACH SCENE EXISTS"].splitlines() if re.match(r"\| \d+ \|", ln)]
            self.assertEqual(len(rows), len(rc["scenes"]))
            self.assertIn("Receipts in, report out.", md)
            self.assertIn("background music: never", md)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
