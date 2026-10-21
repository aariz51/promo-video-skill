"""Tests for the /promo-video creative compiler. Run: python3 -m unittest discover -s tests"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
from helpers import SKILL, Env, fake_watch_script, ffmpeg, has_ffmpeg  # noqa: E402

from promo_engine import adapter, analyzer, artifacts, audio, qa, render, timeline, watcher
from promo_engine.cli import COMMANDS, build_parser, main
from promo_engine.util import PromoError, read_json, write_json
from promo_engine.youtube import parse_youtube_url


def frontmatter(md: str) -> dict:
    end = md.index("\n---", 3)
    out = {}
    for ln in md[3:end].splitlines():
        m = re.match(r"^([\w-]+):\s*(.*)$", ln)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


# 1 ─ command discovery ────────────────────────────────────────────────────────────
class CommandDiscovery(unittest.TestCase):
    def test_skill_is_user_invocable_as_promo_video(self):
        md = (SKILL / "SKILL.md").read_text()
        fm = frontmatter(md)
        self.assertEqual(fm["name"], "promo-video")
        self.assertEqual(fm["user-invocable"], "true")
        self.assertEqual(SKILL.name, fm["name"], "skill folder must match its name for discovery")

    def test_skill_asks_the_inspiration_question_first(self):
        md = (SKILL / "SKILL.md").read_text()
        self.assertIn("Do you have a YouTube video you want to use as visual inspiration?", md)
        first_q = md.index("Do you have a YouTube video")
        self.assertLess(first_q, md.index("## Step 2"), "the inspiration question comes before the work")

    def test_skill_names_both_paths_and_every_artifact(self):
        md = (SKILL / "SKILL.md").read_text()
        for needle in ("YOUTUBE INSPIRATIONAL PROMPT", "PRODUCT PROMO BRIEF", "PRODUCT-SPECIFIC PROMO PROMPT",
                       "MASTER CREATIVE FRAMEWORK", "product-brief.md", "inspiration-analysis.md",
                       "creative-prompt.md", "storyboard.md", "timeline.json", "narration.txt",
                       "render-config.json", "qa-report.md"):
            self.assertIn(needle, md)

    def test_cli_exposes_the_pipeline(self):
        for cmd in ("doctor", "init", "scan", "capture", "watch", "check", "adapt", "compile",
                    "voice", "audio", "render", "qa", "build", "status"):
            self.assertIn(cmd, COMMANDS)
        self.assertEqual(build_parser().parse_args(["build", "--aspect", "9:16"]).aspect, ["9:16"])

    def test_no_single_product_is_hard_coded(self):
        banned = re.compile(r"\b(sonnet|opus|haiku)\b|safemama|pregnan|claude\s+\d", re.I)
        for p in list((SKILL / "engine").rglob("*.py")) + list((SKILL / "renderer" / "src").rglob("*.ts*")) \
                + [SKILL / "framework" / "master-creative-framework.md"]:
            self.assertIsNone(banned.search(p.read_text()), f"product-specific text in {p}")


# 4 ─ YouTube URL validation ───────────────────────────────────────────────────────
class YouTubeUrls(unittest.TestCase):
    def test_accepts_every_single_video_form(self):
        for url in ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
                    "https://youtu.be/dQw4w9WgXcQ?si=abc", "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://www.youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ",
                    "https://www.youtube.com/live/dQw4w9WgXcQ", "<https://youtu.be/dQw4w9WgXcQ>",
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123"):
            self.assertEqual(parse_youtube_url(url).id, "dQw4w9WgXcQ", url)
        self.assertEqual(parse_youtube_url("youtu.be/dQw4w9WgXcQ").url, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_rejects_with_a_reason(self):
        cases = {"": "no inspiration", "https://vimeo.com/123": "not a YouTube", "ftp://youtube.com/watch?v=x": "not a web",
                 "https://www.youtube.com/watch?v=short": "valid video id", "https://www.youtube.com/@somechannel": "channel",
                 "https://www.youtube.com/playlist?list=PL123": "playlist", "https://youtu.be/": "valid video id",
                 "https://evil-youtube.com/watch?v=dQw4w9WgXcQ": "not a YouTube"}
        for url, why in cases.items():
            with self.assertRaises(PromoError, msg=url) as cm:
                parse_youtube_url(url)
            self.assertIn(why, str(cm.exception), url)

    def test_init_rejects_a_bad_url_before_any_work(self):
        env = Env()
        try:
            before = env.ws.config_path.read_text()
            for bad in ("https://www.youtube.com/@somechannel", "ftp://example.com/a.mp4", "./missing-ref.mp4"):
                code = main(["-w", str(env.ws.root), "init", "--product", str(env.product), "--reference", bad])
                self.assertEqual(code, 1, bad)
            self.assertEqual(env.ws.config_path.read_text(), before, "nothing is written for a rejected reference")
        finally:
            env.close()


# 6 ─ product analysis → brief ────────────────────────────────────────────────────
class ProductAnalysis(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_scan_derives_the_product_from_the_repo(self):
        data = analyzer.scan(self.env.product)
        self.assertEqual(data["projectType"], "web-app")
        self.assertIn("Next.js", data["frameworks"])
        self.assertEqual(data["readme"]["title"], "Tallyboard")
        self.assertIn("categorised monthly expense report", data["readme"]["intro"])
        self.assertEqual({r["route"] for r in data["routes"]}, {"/", "/reports"})
        self.assertEqual(data["launch"]["command"], "npm run dev")
        self.assertEqual(data["launch"]["url"], "http://localhost:3100")
        self.assertEqual([l["path"] for l in data["assets"]["logos"]], ["public/logo.png"])
        self.assertEqual(data["assets"]["logos"][0]["size"], [64, 64])
        self.assertEqual(len(data["assets"]["screenshots"]), 2)
        self.assertIn("#1f8a70", [c["value"] for c in data["brand"]["colors"]])
        self.assertEqual({e["name"] for e in data["envVariables"]}, {"DATABASE_URL", "EXPORT_BUCKET"})
        self.assertEqual(data["tests"]["count"], 1)

    def test_scan_never_reads_secrets(self):
        data = analyzer.scan(self.env.product)
        blob = json.dumps(data)
        self.assertNotIn("do-not-read-me", blob)
        self.assertNotIn("sk-fake", blob)
        self.assertIn(".env", data["skippedForSecurity"])
        self.assertIn("api key.txt", data["skippedForSecurity"])

    def test_brief_passes_when_every_claim_is_sourced(self):
        rep = artifacts.check_brief(helpers.BRIEF, self.env.product)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(set(artifacts.parse_claims(helpers.BRIEF)), {"C1", "C2", "C3", "C4"})

    def test_brief_rejects_invented_or_unsourced_claims(self):
        bad = helpers.BRIEF.replace("source: README.md:9", "source: docs/made-up.md") \
                           .replace("source: package.json:3", "source: package.json:999")
        bad = bad.replace("## RESTRICTIONS\n\nNo customer names, no accuracy percentages, no pricing.", "## RESTRICTIONS\n")
        msgs = artifacts.check_brief(bad, self.env.product).summary()
        self.assertIn("C3 cites 'docs/made-up.md', which does not exist", msgs)
        self.assertIn("line 999", msgs)
        self.assertIn("'RESTRICTIONS' is empty", msgs)


# 5 ─ inspiration prompt ──────────────────────────────────────────────────────────
class InspirationPrompt(unittest.TestCase):
    EV = {"duration": 40.0, "transcript": {"available": True, "lines": helpers.TRANSCRIPT}}

    def test_complete_analysis_passes(self):
        rep = artifacts.check_inspiration(helpers.inspiration_md(), self.EV)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(len(artifacts.parse_rules(helpers.inspiration_md())), 12)

    def test_a_summary_is_not_an_analysis(self):
        rep = artifacts.check_inspiration("# YOUTUBE INSPIRATIONAL PROMPT\n\nA cool dark video with nice motion.\n", self.EV)
        self.assertGreaterEqual(len(rep.errors), 12)

    def test_requires_timestamps_rules_and_real_times(self):
        md = helpers.inspiration_md()
        few = re.sub(r"\n(1[0-2]|[4-9])\. R\d+ .*", "", md)
        self.assertIn("needs 10–20 numbered rules", artifacts.check_inspiration(few, self.EV).summary())
        late = md.replace("0:28–0:40 | Lockup", "0:28–2:40 | Lockup")
        self.assertIn("beyond the video's 40s length", artifacts.check_inspiration(late, self.EV).summary())

    def test_copying_the_narration_is_rejected(self):
        md = helpers.inspiration_md().replace("calm confidence", "we built the fastest way to understand your data")
        self.assertIn("copies narration verbatim", artifacts.check_inspiration(md, self.EV).summary())


# 3 + 10 ─ inspiration path through the watch adapter ─────────────────────────────
@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class WatchAdapter(unittest.TestCase):
    def setUp(self):
        self.env = Env(inspiration=True)
        self.video = self.env.tmp / "ref.mp4"
        # Four hard cuts: black → red → blue → white → green, 2 s each.
        parts = []
        for i, c in enumerate(("black", "red", "blue", "white", "green")):
            p = self.env.tmp / f"p{i}.mp4"
            ffmpeg("-f", "lavfi", "-i", f"color=c={c}:s=320x180:d=2:r=25", "-pix_fmt", "yuv420p", str(p))
            parts.append(p)
        lst = self.env.tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(self.video))

    def tearDown(self):
        self.env.close()

    def test_watch_produces_structured_evidence_and_pacing(self):
        script = fake_watch_script(self.env.tmp / "watchskill", video=self.video)
        ev = watcher.watch(self.env.ws, "https://youtu.be/abcdefghijk", script=script)
        self.assertEqual(ev["videoId"], "abcdefghijk")
        self.assertEqual(len(ev["frames"]), 8)
        self.assertEqual(ev["frames"][3]["t"], 15)
        self.assertTrue(ev["transcript"]["available"])
        self.assertEqual(ev["transcript"]["lines"][1]["t"], 6)
        self.assertEqual(ev["pacing"]["cutCount"], 4)
        self.assertAlmostEqual(ev["pacing"]["averageShot"], 2.0, delta=0.1)
        self.assertTrue(self.env.ws.evidence.exists())
        self.assertTrue((self.env.ws.inspiration_dir / "watch-report.md").exists())

    def test_failed_analysis_stops_the_pipeline(self):
        script = fake_watch_script(self.env.tmp / "broken", fail=True)
        with mock.patch.object(watcher, "_fallback_download", return_value=None):
            with self.assertRaises(PromoError) as cm:
                watcher.watch(self.env.ws, "https://youtu.be/abcdefghijk", script=script)
        self.assertIn("Video unavailable", str(cm.exception))
        self.assertIn("No analysis is invented", cm.exception.hint)
        self.assertFalse(self.env.ws.evidence.exists())

    def test_invalid_url_never_reaches_the_watcher(self):
        script = fake_watch_script(self.env.tmp / "unused")
        for bad in ("https://www.youtube.com/@somechannel", "ftp://example.com/v.mp4", "none"):
            with self.assertRaises(PromoError, msg=bad):
                watcher.watch(self.env.ws, bad, script=script)
        self.assertFalse((self.env.ws.inspiration_dir / "watch").exists(), "the watcher never ran")

    def test_missing_watch_skill_explains_how_to_install(self):
        with mock.patch.dict(os.environ, {"PROMO_WATCH_SKILL_DIR": "/nonexistent"}), \
                mock.patch.object(Path, "home", return_value=self.env.tmp):
            with self.assertRaises(PromoError) as cm:
                watcher.find_watch_skill()
        self.assertIn("bradautomates/claude-video", cm.exception.hint)

    def test_report_without_transcript_is_marked_unavailable(self):
        text = (self.env.tmp / "r.md")
        text.write_text("# watch: video report\n\n- **Duration:** 00:10 (10.0s)\n- **Transcript:** none available\n\n"
                        "## Frames\n\n- `/x/f1.jpg` (t=00:02, reason=uniform)\n\n## Transcript\n\n_No transcript available._\n")
        ev = watcher.parse_report(text.read_text())
        self.assertFalse(ev["transcript"]["available"])
        self.assertEqual(ev["duration"], 10.0)


# 2 + 7 ─ creative transformation, both paths ─────────────────────────────────────
class CreativeTransformation(unittest.TestCase):
    def test_no_inspiration_path_uses_the_master_framework(self):
        env = Env().with_artifacts()
        try:
            path = adapter.scaffold(env.ws)
            md = path.read_text()
            self.assertIn("Source of creative structure: MASTER CREATIVE FRAMEWORK", md)
            self.assertEqual(len(adapter.framework_beats()), 13)
            self.assertIn("§4 Hook", md)
            self.assertIn("- C3: Receipts never leave your machine", md)
            rep = artifacts.check_creative(md, claims=artifacts.parse_claims(helpers.BRIEF), source="framework")
            self.assertIn("unfilled placeholders", rep.summary(), "a scaffold is not a finished prompt")
            with self.assertRaises(PromoError):
                adapter.scaffold(env.ws)  # never silently overwrite the agent's work
        finally:
            env.close()

    def test_inspiration_path_rescales_the_source_structure(self):
        env = Env(inspiration=True).with_artifacts()
        try:
            env.ws.inspiration.write_text(helpers.inspiration_md())
            write_json(env.ws.evidence, {"duration": 40.0, "transcript": {"available": True, "lines": helpers.TRANSCRIPT},
                                         "pacing": {"averageShot": 10.0, "cutCount": 3, "quarters": []}})
            md = adapter.scaffold(env.ws).read_text()
            self.assertIn("Source of creative structure: YOUTUBE INSPIRATIONAL PROMPT", md)
            self.assertIn("Target runtime: 40 s", md)  # inside 30–100, so the source length is kept
            self.assertIn("| 3 | 0:14.0–0:28.0 | 0:14.0 Demonstration", md)
            self.assertIn("- R12 — rule number 12", md)
            cfg = json.loads(env.ws.config_path.read_text())
            cfg["duration"] = {"min": 60, "max": 100}
            env.ws.config_path.write_text(json.dumps(cfg))
            md = adapter.scaffold(env.ws, force=True).read_text()
            self.assertIn("time scale ×1.50", md)
            self.assertIn("| 3 | 0:21.0–0:42.0 |", md)
        finally:
            env.close()

    def test_finished_prompt_is_validated_against_brief_and_source(self):
        claims = artifacts.parse_claims(helpers.BRIEF)
        rules = artifacts.parse_rules(helpers.inspiration_md())
        rows = "\n".join(f"| {i} | 0:0{i}–0:1{i} | R{i} | scene | flow | C1 | fade | pop | line |" for i in range(1, 6))
        good = ("# PRODUCT-SPECIFIC PROMO PROMPT\n\n## CORE MESSAGE\n\nReceipts in, report out.\n\n## CREATIVE DNA\n\n"
                + "\n".join(f"- R{i} applied" for i in range(1, 8))
                + "\n\n## PACING PLAN\n\nHook 8 s.\n\n## SCENE PLAN\n\n| # | Time | Beat | Scene | Primitive | Evidence | In | Sound | Narration |\n"
                  "|---|---|---|---|---|---|---|---|---|\n" + rows
                + "\n\n## MOTION & VISUAL SYSTEM\n\nGraphite.\n\n## SOUND DESIGN\n\nNo background music; clicks only.\n\n"
                  "## NARRATION\n\nSparse.\n\n## ORIGINALITY\n\nStructure kept, content replaced.\n\n## FACT CHECK\n\n- C1\n")
        ok = artifacts.check_creative(good, claims=claims, source="inspiration", rules=rules,
                                      transcript=[l["text"] for l in helpers.TRANSCRIPT])
        self.assertTrue(ok.ok, ok.summary())
        bad = good.replace("- C1\n", "- C9\n").replace("No background music; clicks only.", "A warm background music bed.")
        bad = re.sub(r"- R[3-7] applied\n", "", bad) + "\nwe built the fastest way to understand your data\n"
        msgs = artifacts.check_creative(bad, claims=claims, source="inspiration", rules=rules,
                                        transcript=[l["text"] for l in helpers.TRANSCRIPT]).summary()
        self.assertIn("claims not in the brief: C9", msgs)
        self.assertIn("mentions music without excluding it", msgs)
        self.assertIn("carry the inspiration's rules forward", msgs)
        self.assertIn("reuses inspiration narration verbatim", msgs)


# 8 + 9 ─ timeline engine ─────────────────────────────────────────────────────────
class TimelineEngine(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()

    def tearDown(self):
        self.env.close()

    def test_compile_schedules_every_event_on_one_clock(self):
        rc, rep = timeline.compile_timeline(self.env.ws)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual(rc["fps"], 30)
        self.assertEqual(rc["duration"], 64)
        self.assertEqual(rc["durationInFrames"], 64 * 30)
        froms = [s["from"] for s in rc["scenes"]]
        self.assertEqual(froms, [0, 240, 390, 810, 1170, 1440, 1680])
        self.assertEqual(rc["scenes"][1]["transition"], {"type": "light", "frames": 24})
        self.assertEqual(rc["scenes"][0]["transition"]["type"], "none")
        flow = rc["scenes"][2]
        self.assertEqual(flow["props"]["_t"]["steps"], [0.5, 6.4, 12.3])
        chime = [c for c in rc["sound"]["cues"] if c["fx"] == "chime" and c["scene"] == "flow"]
        self.assertEqual(chime[0]["at"], 13 + 12.3)  # the result resolves on the same clock as the picture
        self.assertAlmostEqual(rc["scenes"][3]["props"]["_media"]["screenshots/dashboard.png"], 1.6)
        lines = rc["narration"]["lines"]
        self.assertEqual([l["scene"] for l in lines], ["hook", "flow", "screen", "lockup"])
        self.assertEqual(lines[0]["at"], 5.2)
        self.assertTrue(all(a["windowEnd"] < b["at"] for a, b in zip(lines, lines[1:])))
        self.assertIn("| 3 | 0:13.0–0:27.0 | flow | flow |", self.env.ws.storyboard.read_text())
        self.assertIn("Background music: none", self.env.ws.storyboard.read_text())
        self.assertIn("[0:05.2] Every month ends the same way.", self.env.ws.narration.read_text())

    def test_compile_is_deterministic(self):
        timeline.compile_timeline(self.env.ws)
        a = self.env.ws.render_config.read_text()
        timeline.compile_timeline(self.env.ws)
        self.assertEqual(a, self.env.ws.render_config.read_text())

    def _errors(self, mutate) -> str:
        tl = helpers.timeline()
        mutate(tl)
        self.env.ws.timeline.write_text(json.dumps(tl))
        _, rep = timeline.compile_timeline(self.env.ws)
        self.assertFalse(rep.ok)
        return rep.summary()

    def test_missing_asset_is_an_error_not_a_blank(self):
        msg = self._errors(lambda tl: tl["scenes"][3]["props"].update(media="screenshots/nope.png"))
        self.assertIn("missing asset 'screenshots/nope.png'", msg)

    def test_unsupported_media_is_rejected(self):
        (self.env.ws.assets / "clip.avi").write_bytes(b"0")
        self.assertIn("unsupported media", self._errors(lambda tl: tl["scenes"][3]["props"].update(media="clip.avi")))

    def test_numbers_need_a_source(self):
        def add_number(tl):
            tl["scenes"][4]["claims"] = []
            tl["scenes"][4]["props"]["text"] = "Reports in 3 seconds."
        self.assertIn("without citing a claim", self._errors(add_number))
        self.assertIn("claim C9 is not in", self._errors(lambda tl: tl["scenes"][2].update(claims=["C9"])))

    def test_malformed_scenes_are_named(self):
        msg = self._errors(lambda tl: (tl["scenes"][0].update(kind="slideshow"), tl["scenes"][2]["props"].update(steps=[{"label": "a"}]),
                                       tl["scenes"][4]["props"].update(text="x" * 200), tl["scenes"].append(dict(tl["scenes"][5]))))
        self.assertIn("unknown kind 'slideshow'", msg)
        self.assertIn("props.steps must be a list of 2–5 items", msg)
        self.assertIn("holds 90", msg)
        self.assertIn("duplicate id 'compare'", msg)

    def test_timing_and_narration_limits(self):
        self.assertIn("outside the configured", self._errors(lambda tl: [tl["scenes"][i].update(duration=30) for i in (2, 3, 4)]))
        self.assertIn("narration needs", self._errors(lambda tl: tl["scenes"][1].update(narration="one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen")))
        self.assertIn("disabled without a reason", self._errors(lambda tl: tl.update(narration={"enabled": False})))
        self.assertIn("terminal content needs", self._errors(lambda tl: tl["scenes"].__setitem__(4, {
            "id": "term", "kind": "terminal", "duration": 3, "purpose": "demo",
            "props": {"lines": [{"type": "cmd", "text": "x" * 60}] * 4}})))

    def test_wordzoom_schedules_the_fly_through(self):
        def hook(tl, word="report", dur=9):
            tl["scenes"][0] = {"id": "hook", "kind": "wordzoom", "duration": dur, "purpose": "hook",
                               "props": {"line": "receipts become", "then": "a monthly report", "word": word}}
        tl = helpers.timeline()
        hook(tl)
        self.env.ws.timeline.write_text(json.dumps(tl))
        rc, rep = timeline.compile_timeline(self.env.ws)
        self.assertTrue(rep.ok, rep.summary())
        t = rc["scenes"][0]["props"]["_t"]
        self.assertLess(t["then"], t["select"])
        self.assertLess(t["select"], t["zoom"][0])
        self.assertLess(t["zoom"][1], t["name"])
        fx = [c["fx"] for c in rc["sound"]["cues"] if c["scene"] == "hook"]
        self.assertIn("click", fx)
        self.assertIn("whoosh", fx)
        self.assertIn("must appear", self._errors(lambda tl: hook(tl, word="invoice")))
        self.assertIn("wordzoom needs", self._errors(lambda tl: hook(tl, dur=4)))

    def test_unknown_sound_effect_and_music_are_impossible(self):
        self.assertIn("unknown sound effect 'music'", self._errors(lambda tl: tl["scenes"][0].update(sfx=[{"fx": "music", "at": 1}])))


# 11 ─ rendering failures ─────────────────────────────────────────────────────────
class RenderFailures(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()
        timeline.compile_timeline(self.env.ws)

    def tearDown(self):
        self.env.close()

    def test_renderer_failure_surfaces_the_log(self):
        fake = self.env.tmp / "renderer"
        (fake / "node_modules" / "@remotion" / "cli").mkdir(parents=True)
        bindir = self.env.tmp / "bin"
        bindir.mkdir()
        npx = bindir / "npx"
        npx.write_text("#!/bin/sh\necho 'Error: Composition Promo16x9 crashed at frame 812' >&2\nexit 1\n")
        npx.chmod(npx.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}"}
        self.env.ws.master_audio.parent.mkdir(parents=True, exist_ok=True)
        self.env.ws.master_audio.write_bytes(b"RIFF")  # the audio step ran; only the renderer fails
        with mock.patch.object(render, "RENDERER_DIR", fake), mock.patch.dict(os.environ, env):
            with self.assertRaises(PromoError) as cm:
                render.render(self.env.ws, "16:9")
        self.assertIn("crashed at frame 812", str(cm.exception))
        self.assertTrue((self.env.ws.root / "build" / "render-16x9.log").exists())

    def test_low_disk_is_refused_before_rendering(self):
        with mock.patch.object(render, "ensure_renderer"), mock.patch.object(render, "free_gb", return_value=0.2):
            with self.assertRaises(PromoError) as cm:
                render.render(self.env.ws, "16:9")
        self.assertIn("free disk space", cm.exception.hint)

    def test_missing_asset_blocks_staging(self):
        (self.env.ws.assets / "screenshots" / "dashboard.png").unlink()
        with self.assertRaises(PromoError) as cm:
            render.stage(self.env.ws, read_json(self.env.ws.render_config))
        self.assertIn("screen: screenshots/dashboard.png", str(cm.exception))

    def test_unsupported_aspect(self):
        with self.assertRaises(PromoError):
            render.render(self.env.ws, "4:3")


# 12 ─ QA ─────────────────────────────────────────────────────────────────────────
@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class QualityAssurance(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()
        self.rc, _ = timeline.compile_timeline(self.env.ws)
        # Keep the film short for QA tests: 4 s, two scenes.
        self.rc["scenes"] = self.rc["scenes"][:2]
        self.rc["scenes"][0]["durationInFrames"], self.rc["scenes"][1]["from"], self.rc["scenes"][1]["durationInFrames"] = 60, 60, 60
        self.rc.update(duration=4.0, durationInFrames=120)
        self.rc["narration"]["lines"] = [{"at": 0.5, "text": "x", "scene": "hook", "windowEnd": 1.9}]
        write_json(self.env.ws.render_config, self.rc)

    def tearDown(self):
        self.env.close()

    def _video(self, name, size="1920x1080", dur=4, rate=30, audio=True):
        """audio=True: one 0.3 s effect at 1.0 s (matches `pop` in MANIFEST); "noise": a bed."""
        out = self.env.ws.out_dir / name
        out.parent.mkdir(parents=True, exist_ok=True)
        args = ["-f", "lavfi", "-i", f"testsrc2=s={size}:d={dur}:r={rate}"]
        if audio == "noise":
            args += ["-f", "lavfi", "-i", f"anoisesrc=d={dur}:a=0.2:seed=1", "-c:a", "aac", "-shortest"]
        elif audio:
            args += ["-f", "lavfi", "-i", f"sine=f=660:d=0.3,adelay=1000|1000,apad=whole_dur={dur}",
                     "-c:a", "aac", "-shortest"]
        ffmpeg(*args, "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "ultrafast", str(out))
        return out

    def test_valid_render_passes_the_file_checks(self):
        rep, facts = qa.check_video(self._video("promo-16x9.mp4"), "16:9", self.rc)
        self.assertTrue(rep.ok, rep.summary())
        self.assertEqual((facts["width"], facts["height"], facts["fps"]), (1920, 1080, 30.0))

    def test_wrong_size_rate_length_and_no_audio_fail(self):
        rep, _ = qa.check_video(self._video("bad.mp4", size="1280x720", dur=3, rate=25, audio=False), "16:9", self.rc)
        msgs = rep.summary()
        for needle in ("resolution 1280×720", "frame rate 25.00", "duration 3.00s", "no audio stream"):
            self.assertIn(needle, msgs)

    def _master(self, extra: list[str]) -> Path:
        self.env.ws.master_audio.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg("-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo:d=4", *extra, str(self.env.ws.master_audio))
        return self.env.ws.master_audio

    MANIFEST = {"music": False, "sources": [{"kind": "sfx", "source": "sfx/pop.wav", "at": 1.0, "seconds": 0.3}]}

    def test_background_music_is_detected(self):
        manifest = self.MANIFEST
        clean = self._master(["-f", "lavfi", "-i", "sine=f=660:d=0.3", "-filter_complex", "[1]adelay=1000|1000[b];[0][b]amix=inputs=2:normalize=0"])
        self.assertTrue(qa.check_no_music(manifest, clean, self.rc).ok)
        bed = self._master(["-f", "lavfi", "-i", "sine=f=220:d=4", "-filter_complex", "[0][1]amix=inputs=2:normalize=0"])
        self.assertIn("possible bed/music", qa.check_no_music(manifest, bed, self.rc).summary())
        bad = {"music": False, "sources": [{"kind": "sfx", "source": "sfx/track.mp3", "at": 0, "seconds": 45.0}]}
        # The encoded film is checked too: a bed muxed after the mix is still caught.
        self.assertIn("possible bed/music", qa.check_no_music(manifest, self._video("bed.mp4", audio="noise"), self.rc).summary())
        msgs = qa.check_no_music(bad, clean, self.rc).summary()
        self.assertIn("unknown effect source", msgs)
        self.assertIn("long files can carry music", msgs)

    def test_narration_must_sit_inside_its_scene(self):
        good = {"lines": [{"at": 0.5, "seconds": 1.2, "scene": "hook"}]}
        self.assertTrue(qa.check_narration(good, self.rc).ok)
        late = {"lines": [{"at": 1.5, "seconds": 2.0, "scene": "hook"}]}
        self.assertIn("outside its scene", qa.check_narration(late, self.rc).summary())
        self.assertIn("0 voice lines rendered", qa.check_narration({"lines": []}, self.rc).summary())

    def test_full_qa_writes_the_report(self):
        self._video("promo-16x9.mp4")
        self._master(["-f", "lavfi", "-i", "sine=f=660:d=0.3", "-filter_complex", "[1]adelay=1000|1000[b];[0][b]amix=inputs=2:normalize=0"])
        write_json(self.env.ws.root / "build" / "audio-manifest.json", self.MANIFEST)
        self.env.ws.vo_dir.mkdir(parents=True, exist_ok=True)
        write_json(self.env.ws.vo_dir / "manifest.json", {"engine": "say", "lines": [{"at": 0.5, "seconds": 1.0, "scene": "hook"}]})
        rep = qa.run_qa(self.env.ws, {"16:9": self.env.ws.out_dir / "promo-16x9.mp4"})
        self.assertTrue(rep.ok, rep.summary())
        report = self.env.ws.qa_report.read_text()
        self.assertEqual(self.env.ws.qa_report.name, "TEST_REPORT.md")
        self.assertIn("Result: **PASS**", report)
        val = read_json(self.env.ws.qa_dir / "validation.json")
        self.assertEqual(val["result"], "PASS")
        self.assertEqual({c["id"]: c["status"] for c in val["checks"]},
                         {"render": "PASS", "encoding": "PASS", "timeline": "PASS", "narration": "PASS", "audio": "PASS"})
        self.assertEqual(len(list((self.env.ws.qa_dir / "frames" / "16x9").glob("*.jpg"))), 4)
        missing = qa.run_qa(self.env.ws, {"16:9": self.env.ws.out_dir / "nope.mp4"})
        self.assertIn("was not produced", missing.summary())


class AudioMix(unittest.TestCase):
    @unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
    def test_mix_is_effects_and_voice_only(self):
        env = Env().with_artifacts()
        try:
            rc, _ = timeline.compile_timeline(env.ws)
            rc["narration"]["enabled"] = False
            m = audio.build_master(env.ws, rc)
            self.assertFalse(m["music"])
            self.assertEqual({s["kind"] for s in m["sources"]}, {"sfx"})
            self.assertTrue(qa.check_no_music(m, env.ws.master_audio, rc).ok)
            rc["narration"]["enabled"] = True
            with self.assertRaises(PromoError):
                audio.build_master(env.ws, rc)  # narration planned but never rendered
        finally:
            env.close()


class RendererContract(unittest.TestCase):
    def test_every_engine_kind_has_a_renderer_scene(self):
        registry = (SKILL / "renderer" / "src" / "scenes" / "index.tsx").read_text()
        for kind in timeline.KINDS:
            self.assertRegex(registry, rf"\n\s+{kind}: \w+,", kind)

    def test_every_format_is_a_composition_of_the_same_film(self):
        from promo_engine.config import ASPECTS, render_scale
        root = (SKILL / "renderer" / "src" / "Root.tsx").read_text()
        want = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080),
                "store-portrait": (886, 1920), "store-landscape": (1920, 886)}
        self.assertEqual({a: (v["width"], v["height"]) for a, v in ASPECTS.items()}, want)
        for a, v in ASPECTS.items():
            self.assertIn(f'id: "{v["id"]}", width: {v["width"]}, height: {v["height"]}', root)
            for q in ("draft", "final"):  # every render size is even (H.264 4:2:0)
                s = render_scale(a, q)
                self.assertTrue((v["width"] * s) % 2 == 0 and (v["height"] * s) % 2 == 0, (a, q, s))
        self.assertEqual(root.count("component={Film}"), 1, "one Film component behind every composition")

    def test_no_nondeterminism_in_the_renderer(self):
        for p in (SKILL / "renderer" / "src").rglob("*.ts*"):
            text = p.read_text()
            self.assertNotIn("Math.random", text, p)
            self.assertNotIn("Date.now", text, p)

    def test_sample_props_match_the_contract(self):
        sample = json.loads((SKILL / "renderer" / "src" / "sample" / "render-config.json").read_text())
        self.assertEqual(sample["durationInFrames"], sum(s["durationInFrames"] for s in sample["scenes"]))
        self.assertTrue(all(s["kind"] in timeline.KINDS for s in sample["scenes"]))


# End to end: compile → voice → audio → render → QA with the real renderer.
@unittest.skipUnless(os.environ.get("PROMO_E2E") == "1", "set PROMO_E2E=1 to render a real film (slow)")
class EndToEnd(unittest.TestCase):
    def test_build_renders_a_verified_film(self):
        env = Env().with_artifacts()
        try:
            cfg = json.loads(env.ws.config_path.read_text())
            cfg["render"] = {"quality": "draft", "outputDir": "out"}
            cfg["voice"] = {"provider": "say" if shutil.which("say") else "none", "voice": None, "direction": "calm"}
            env.ws.config_path.write_text(json.dumps(cfg))
            code = main(["-w", str(env.ws.root), "build"])
            self.assertEqual(code, 0, env.ws.qa_report.read_text() if env.ws.qa_report.exists() else "no report")
            self.assertIn("Result: **PASS**", env.ws.qa_report.read_text())
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
