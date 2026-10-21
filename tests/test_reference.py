"""Reference analysis on synthetic clips whose structure is known exactly.

The fixtures are rendered with ffmpeg at test time (no downloads, no binaries in git):
`rapid` (five scenes on hard cuts, internal motion, a camera pan, a fade to black) and
`slow` (fade in, a dissolve, a wipe, a dip to black, long holds). The analyzer must
recover their boundaries, transition types and camera moves from the pixels.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
from helpers import Env, fake_watch_script, ffmpeg, has_ffmpeg  # noqa: E402

from promo_engine import reference, watcher
from promo_engine.util import PromoError, read_json, write_json

FRAME = 1 / helpers.REF_FPS
_CACHE: dict[str, tuple[Path, dict, dict]] = {}
_TMP = Path(tempfile.mkdtemp(prefix="promo-ref-"))


def analysed(profile: str) -> tuple[Path, dict, dict]:
    """(video, ground truth, breakdown) — rendered and analysed once per test run."""
    if profile not in _CACHE:
        video = _TMP / f"{profile}.mp4"
        truth = helpers.make_reference(video, profile)
        bd = reference.analyze(video, _TMP / profile)
        _CACHE[profile] = (video, truth, bd)
    return _CACHE[profile]


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class Metadata(unittest.TestCase):
    def test_metadata_comes_from_the_file(self):
        video, truth, bd = analysed("rapid")
        m = bd["metadata"]
        self.assertAlmostEqual(m["duration"], truth["duration"], delta=0.05)
        self.assertEqual((m["width"], m["height"], m["aspect"], m["fps"]), (320, 180, "16:9", 25.0))
        self.assertTrue(m["audio"]["present"])
        self.assertEqual(m["videoCodec"], "h264")
        self.assertFalse(m["captions"]["available"], "no transcript was supplied, and it says so")
        self.assertGreater(bd["analysis"]["decodedSeconds"], truth["duration"] - 0.1)


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class Boundaries(unittest.TestCase):
    def _match(self, profile: str, tol: float):
        _, truth, bd = analysed(profile)
        got = [(t["start"], t["end"], t["type"]) for t in bd["transitions"]]
        self.assertEqual(len(bd["scenes"]), truth["scenes"], got)
        self.assertEqual([g[2] for g in got], truth["types"])
        for (a, b, _), (ta, tb) in zip(got, truth["boundaries"]):
            self.assertAlmostEqual(a, ta, delta=tol, msg=got)
            self.assertAlmostEqual(b, tb, delta=tol, msg=got)
        return bd

    def test_hard_cuts_are_found_to_the_frame(self):
        self._match("rapid", tol=FRAME + 1e-6)

    def test_gradual_transitions_are_classified(self):
        bd = self._match("slow", tol=2 * FRAME + 1e-6)
        self.assertEqual(bd["transitions"][1]["type"], "wipe-left", "direction comes from the pixels")
        self.assertGreater(bd["transitions"][0]["detail"]["alpha"][-1], bd["transitions"][0]["detail"]["alpha"][0])

    def test_motion_inside_a_scene_is_not_a_boundary(self):
        _, _, bd = analysed("rapid")
        motion = bd["scenes"][1]  # testsrc2: moving elements for 1.6 s
        self.assertAlmostEqual(motion["duration"], 1.6, delta=FRAME)
        self.assertGreater(motion["measured"]["motionEnergy"], 0.004)

    def test_camera_moves_are_measured(self):
        _, _, bd = analysed("rapid")
        pan = bd["scenes"][3]
        self.assertIn("pan: content moves left", pan["measured"]["camera"])
        self.assertAlmostEqual(pan["measured"]["cameraEstimate"]["dx"], -0.57, delta=0.08)  # 120 px/s × 1.52 s / 320
        self.assertNotIn("tilt", pan["measured"]["camera"])
        for sc in (bd["scenes"][0], bd["scenes"][2]):
            self.assertEqual(sc["measured"]["camera"], "static hold")

    def test_opening_and_closing_conventions(self):
        _, _, rapid = analysed("rapid")
        _, _, slow = analysed("slow")
        self.assertEqual(rapid["conventions"]["closing"]["type"], "fade-out")
        self.assertAlmostEqual(rapid["conventions"]["closing"]["start"], 6.2, delta=2 * FRAME)
        self.assertIn("fades out", rapid["scenes"][-1]["measured"]["fade"])
        self.assertEqual(slow["conventions"]["opening"]["type"], "fade-in")
        self.assertIsNone(slow["conventions"]["closing"])

    def test_colour_is_measured(self):
        _, _, bd = analysed("slow")
        self.assertEqual(bd["scenes"][1]["measured"]["mean"][:3], "#E4")  # orange 0xE67E22
        self.assertGreater(bd["scenes"][3]["measured"]["brightness"], 0.6)  # light grey


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class Evidence(unittest.TestCase):
    def test_frames_have_valid_timestamps_and_exist(self):
        for profile in ("rapid", "slow"):
            _, truth, bd = analysed(profile)
            root = _TMP / profile
            for sc in bd["scenes"]:
                self.assertTrue(sc["frames"], sc["id"])
                for f in sc["frames"]:
                    self.assertTrue(sc["start"] - 1e-6 <= f["t"] <= sc["end"] + 1e-6, (sc["id"], f))
                    self.assertTrue((root / f["file"]).stat().st_size > 0)
                    self.assertIn(f"t{f['t']:07.2f}".replace(".", "_"), f["file"])
            for tr in bd["transitions"]:
                roles = [f["role"] for f in tr["frames"]]
                self.assertEqual(roles, ["before", "after"] if tr["type"] == "cut" else ["before", "during", "after"])

    def test_contact_sheets_are_real_images_with_labels(self):
        _, _, bd = analysed("slow")
        kinds = {s["kind"] for s in bd["contactSheets"]}
        self.assertEqual(kinds, {"scenes", "transitions", "uniform"})
        for sheet in bd["contactSheets"]:
            p = _TMP / "slow" / sheet["file"]
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(p)],
                                 capture_output=True, text=True).stdout.strip()
            w, h = (int(x) for x in out.split(","))
            self.assertEqual(w, 4 * reference.CELL_W)
            self.assertGreater(h, 0)
            self.assertTrue(all("label" in c and "t" in c for c in sheet["cells"]))

    def test_coverage_spans_the_whole_film(self):
        for profile in ("rapid", "slow"):
            _, truth, bd = analysed(profile)
            self.assertEqual(reference.validate(bd, _TMP / profile), [])
            ts = [u["t"] for u in bd["uniform"]]
            self.assertLess(ts[0], truth["duration"] * 0.1)
            self.assertGreater(ts[-1], truth["duration"] * 0.9)
            self.assertEqual(ts, sorted(ts))
            starts = [s["start"] for s in bd["scenes"]]
            self.assertEqual(starts, sorted(starts))

    def test_validation_rejects_broken_breakdowns(self):
        _, _, bd = analysed("slow")
        root = _TMP / "slow"
        bad = json.loads(json.dumps(bd))
        bad["scenes"][1]["start"] = bad["scenes"][0]["start"] + 0.1
        self.assertTrue(any("overlaps" in e or "does not sit" in e for e in reference.validate(bad, root)))
        bad = json.loads(json.dumps(bd))
        bad["transitions"][0]["to"] = "S09"
        self.assertTrue(any("unknown scene" in e for e in reference.validate(bad, root)))
        bad = json.loads(json.dumps(bd))
        bad["scenes"][0]["frames"] = [{"t": 1, "file": "frames/nope.jpg"}]
        self.assertTrue(any("missing evidence" in e for e in reference.validate(bad, root)))
        bad = json.loads(json.dumps(bd))
        bad["scenes"] = []
        self.assertIn("no scenes", reference.validate(bad, root))

    def test_motion_spec_is_consumable_and_differs_by_reference(self):
        _, _, rapid = analysed("rapid")
        _, _, slow = analysed("slow")
        for bd in (rapid, slow):
            ms = json.loads((_TMP / ("rapid" if bd is rapid else "slow") / "motion-spec.json").read_text())
            for key in ("averageScene", "sceneDurations", "boundariesPerMinute", "byQuarter", "beatIntervals",
                        "transitionVocabulary", "cameraVocabulary", "opening", "closing"):
                self.assertIn(key, ms)
        self.assertEqual(rapid["motionSpec"]["hardCutShare"], 1.0)
        self.assertEqual(slow["motionSpec"]["hardCutShare"], 0.0)
        self.assertLess(rapid["motionSpec"]["averageScene"], slow["motionSpec"]["averageScene"])
        self.assertIn("pan", rapid["motionSpec"]["cameraVocabulary"])


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class CacheAndFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-ref-x-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_results_are_cached_by_fingerprint(self):
        video = self.tmp / "r.mp4"
        helpers.make_reference(video, "slow")
        first = reference.analyze(video, self.tmp / "out")
        t0 = time.monotonic()
        again = reference.analyze(video, self.tmp / "out")
        self.assertTrue(again["cached"])
        self.assertLess(time.monotonic() - t0, 1.0)
        self.assertEqual(first["fingerprint"], again["fingerprint"])
        (self.tmp / "out" / again["scenes"][0]["frames"][0]["file"]).unlink()
        self.assertFalse(reference.analyze(video, self.tmp / "out")["cached"], "missing evidence → recompute")
        with open(video, "ab") as fh:
            fh.write(b"\0")  # different bytes (still decodable), so a different fingerprint
        changed = reference.analyze(video, self.tmp / "out")
        self.assertFalse(changed["cached"])
        self.assertNotEqual(changed["fingerprint"], first["fingerprint"])

    def test_truncated_and_malformed_files_fail_loudly(self):
        video = self.tmp / "r.mp4"
        helpers.make_reference(video, "rapid")
        cut = self.tmp / "cut.mp4"
        cut.write_bytes(video.read_bytes()[: video.stat().st_size // 3])
        fake = self.tmp / "fake.mp4"
        fake.write_text("not a video")
        for bad in (cut, fake, self.tmp / "missing.mp4"):
            with self.assertRaises(PromoError, msg=bad.name):
                reference.analyze(bad, self.tmp / f"out-{bad.stem}")
            self.assertFalse((self.tmp / f"out-{bad.stem}" / "breakdown.json").exists())

    def test_missing_ffmpeg_is_reported(self):
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(PromoError) as cm:
                reference.probe(self.tmp / "x.mp4")
        self.assertIn("ffmpeg", str(cm.exception))


@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class WatchIntegration(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.video = self.env.tmp / "ref.mp4"
        helpers.make_reference(self.video, "slow")

    def tearDown(self):
        self.env.close()

    def test_local_reference_without_the_watch_skill_is_measured_honestly(self):
        with mock.patch.object(watcher, "find_watch_skill", side_effect=PromoError("not installed")):
            ev = watcher.watch(self.env.ws, str(self.video))
        self.assertFalse(ev["watch"]["used"])
        self.assertIn("not installed", ev["transcript"]["source"])
        bd = read_json(self.env.ws.reference_dir / "breakdown.json")
        self.assertEqual(len(bd["scenes"]), 4)
        self.assertEqual(ev["breakdown"], "reference/breakdown.json")

    def test_url_without_watch_or_ytdlp_stops_with_a_reason(self):
        with mock.patch.object(watcher, "find_watch_skill", side_effect=PromoError("not installed")), \
                mock.patch.object(watcher.shutil, "which", return_value=None):
            with self.assertRaises(PromoError) as cm:
                watcher.watch(self.env.ws, "https://vimeo.com/76979871")
        self.assertIn("No analysis is invented", cm.exception.hint)
        self.assertFalse((self.env.ws.reference_dir / "breakdown.json").exists())

    def test_watch_evidence_and_measurement_together_and_reuse(self):
        script = fake_watch_script(self.env.tmp / "watchskill", video=self.video)
        ev = watcher.watch(self.env.ws, "https://youtu.be/abcdefghijk", script=script)
        self.assertTrue(ev["watch"]["used"])
        self.assertTrue(ev["transcript"]["available"])
        self.assertEqual(ev["reference"]["metadata"]["captions"]["available"], True)
        self.assertEqual([t["type"] for t in ev["reference"]["transitions"]], ["dissolve", "wipe-left", "dip-black"])
        broken = fake_watch_script(self.env.tmp / "broken", fail=True)
        again = watcher.watch(self.env.ws, "https://youtu.be/abcdefghijk", script=broken)  # no second download
        self.assertEqual(again["watch"]["note"], "reused")
        self.assertTrue(again["reference"]["cached"])


if __name__ == "__main__":
    unittest.main()
