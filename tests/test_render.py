"""Real renders: the CLI, Remotion and ffmpeg, end to end. Slow, so opt-in:

    PROMO_RENDER=1 python3 -m unittest tests.test_render

Covers the autonomous integration run, frame-level animation checks, determinism, the
three audio modes as encoded files, the reference-driven integration run (synthetic
reference → measured breakdown → direction → storyboard → film → fidelity), and the exact
App Store sizes. Nothing here calls a paid API: voice-over uses macOS `say` when present,
otherwise the user-recordings path with generated tones.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import films  # noqa: E402
import helpers  # noqa: E402
from test_direction import fill_direction, fill_timeline  # noqa: E402

from promo_engine import adapter, analyzer, direction, reference
from promo_engine.cli import main
from promo_engine.config import Workspace
from promo_engine.util import RENDERER_DIR, read_json, write_json


def screenshots_by(manifest: dict) -> dict:
    return {s["id"]: s for s in manifest["screenshots"]}

RUN = os.environ.get("PROMO_RENDER") == "1"
READY = (RENDERER_DIR / "node_modules" / "@remotion" / "cli").is_dir() and helpers.has_ffmpeg()
skip = unittest.skipUnless(RUN and READY, "set PROMO_RENDER=1 (needs renderer node_modules and ffmpeg)")


def probe(path: Path) -> dict:
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json",
                                      str(path)], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    return {"w": v["width"], "h": v["height"], "fps": num / den, "duration": float(v.get("duration") or 0),
            "audio": a, "size": path.stat().st_size}


def frame_luma(path: Path, t: float) -> list[float]:
    raw = reference._frame_at(path, t, reference.SIG_W, reference.SIG_H)
    assert raw is not None, f"no frame at {t}"
    return reference._luma(raw)


def product(tmp: Path, *, audio: str, formats=("16:9",), reference_arg="none", runtime="10-20",
            web: bool = False) -> Workspace:
    """The fixture product, initialised, through the discovery stage. With `web`, the product is a
    real local app that discovery launches, inspects and captures; otherwise discovery runs on the
    codebase only (recorded as such)."""
    prod = helpers.make_web_product(tmp / "tallyboard", helpers.free_port()) if web else helpers.make_product(tmp / "tallyboard")
    ws = Workspace.at(prod / "promo")
    args = ["-w", str(ws.root), "init", "--product", str(prod), "--name", "Tallyboard", "--reference", reference_arg,
            "--audio", audio, "--formats", *formats]
    if reference_arg == "none":
        args += ["--runtime", runtime]
    if audio == "voiceover":
        args += ["--provider", "say" if shutil.which("say") else "files"]
    assert main(args) == 0
    ws.brief.write_text(helpers.BRIEF)
    (ws.assets / "screenshots").mkdir(parents=True, exist_ok=True)
    shutil.copy(prod / "public" / "screenshots" / "dashboard.png", ws.assets / "screenshots" / "dashboard.png")
    assert main(["-w", str(ws.root), "discover", "--no-mobile"] + ([] if web else ["--no-launch"])) == 0
    return ws


def mean_rgb(path: Path, t: float, box=None) -> tuple[float, float, float]:
    raw = reference._frame_at(path, t, 64, 36)
    px = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    if box:
        x0, y0, x1, y1 = box
        px = [p for k, p in enumerate(px) if x0 <= k % 64 < x1 and y0 <= k // 64 < y1]
    return tuple(sum(c[j] for c in px) / len(px) / 255 for j in range(3))


def has_colour(path: Path, t: float, hexv: str, tol: int = 40) -> bool:
    raw = reference._frame_at(path, t, 480, 270)
    want = tuple(int(hexv[i:i + 2], 16) for i in (1, 3, 5))
    return any(all(abs(raw[i + j] - want[j]) <= tol for j in range(3)) for i in range(0, len(raw), 3))


def voice_files(ws: Workspace, n: int) -> None:
    """Recordings for the `files` provider (CI without macOS): short tones."""
    (ws.assets / "vo").mkdir(parents=True, exist_ok=True)
    for i in range(n):
        helpers.ffmpeg("-f", "lavfi", "-i", f"sine=f={220 + 40 * i}:d=1.0", "-ar", "48000", "-ac", "2",
                       str(ws.assets / "vo" / f"{i:02d}.wav"))


@skip
class AutonomousFilm(unittest.TestCase):
    """E2E-A: product fixture → scan → brief → creative prompt → timeline → compile →
    voice/audio (effects) → render → QA, through the CLI exactly as the skill runs it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="promo-e2e-a-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)  # runs even if setUpClass fails
        cls.ws = ws = product(cls.tmp, audio="effects", web=True)
        w = ["-w", str(ws.root)]
        assert main(w + ["scan"]) == 0
        assert main(w + ["check", "brief"]) == 0
        assert main(w + ["adapt"]) == 0
        ws.creative.write_text(films.complete_creative_prompt(ws.creative.read_text()))
        assert main(w + ["check", "creative"]) == 0
        ws.timeline.write_text(json.dumps(films.with_real_screen(films.COMPACT, "web-reports"), indent=2))
        assert main(w + ["check", "timeline"]) == 0
        cls.code = main(w + ["build", "--quality", "draft"])
        cls.video = ws.out_dir / "promo-16x9-draft.mp4"
        cls.rc = read_json(ws.render_config)

    def test_build_passes_qa_with_every_check(self):
        self.assertEqual(self.code, 0, self.ws.qa_report.read_text() if self.ws.qa_report.exists() else "no report")
        val = read_json(self.ws.qa_dir / "validation.json")
        self.assertEqual(val["result"], "PASS")
        self.assertEqual({c["status"] for c in val["checks"]}, {"PASS"})
        self.assertIn("Result: **PASS**", self.ws.qa_report.read_text())
        self.assertTrue(self.ws.direction.read_text().startswith(direction.HEADER_A))

    def test_encoded_file(self):
        p = probe(self.video)
        self.assertEqual((p["w"], p["h"], p["fps"]), (960, 540, 30.0))  # draft = half of 1920×1080
        self.assertAlmostEqual(p["duration"], self.rc["duration"], delta=1 / 30 + 0.01)
        self.assertGreater(p["size"], 100_000)
        self.assertEqual(p["audio"]["codec_name"], "aac")
        dec = subprocess.run(["ffmpeg", "-v", "error", "-i", str(self.video), "-f", "null", "-"], capture_output=True, text=True)
        self.assertEqual(dec.returncode, 0)
        self.assertEqual(dec.stderr.strip(), "", "decodes to the last frame without errors")
        n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "default=nw=1:nk=1", str(self.video)], capture_output=True, text=True)
        self.assertEqual(int(n.stdout.strip()), self.rc["durationInFrames"])

    def test_every_scene_animates_and_every_transition_is_real(self):
        val = read_json(self.ws.qa_dir / "validation.json")
        motion = val["videos"]["16:9"]["motion"]
        self.assertEqual([m["scene"] for m in motion], [s["id"] for s in self.rc["scenes"]])
        for m in motion:
            self.assertGreater(m["change"], 0.004, m)
            self.assertGreater(m["detail"], 0.0018, m)
        observed = {t["scene"]: t["observed"] for t in val["videos"]["16:9"]["transitions"]}
        self.assertEqual(observed["flow"], "wipe-right")
        self.assertEqual(observed["lockup"], "dip-black")
        self.assertIn(observed["title"], ("dissolve", "gradual"))

    def test_frames_around_key_moments(self):
        fps = self.rc["fps"]
        sc = {s["id"]: s for s in self.rc["scenes"]}
        t = lambda sid, frac: (sc[sid]["from"] + sc[sid]["durationInFrames"] * frac) / fps  # noqa: E731
        # The lockup builds: its first frames differ from its settled end.
        self.assertGreater(reference._mad(frame_luma(self.video, t("lockup", 0.3)), frame_luma(self.video, t("lockup", 0.95))), 0.004)
        # The dip passes through black at its midpoint, and both sides are lighter.
        mid = (sc["lockup"]["from"] + sc["lockup"]["transition"]["frames"] / 2) / fps
        dark = sum(frame_luma(self.video, mid)) / (reference.SIG_W * reference.SIG_H)
        before = sum(frame_luma(self.video, t("flow", 0.8))) / (reference.SIG_W * reference.SIG_H)
        self.assertLess(dark, 0.4 * before)
        # Part-way through the wipe (it eases out, so early) the edge travelling right has
        # revealed the new picture on the left while the right still shows the old one.
        a, n = sc["flow"]["from"], sc["flow"]["transition"]["frames"]
        mid_f, old, new = (frame_luma(self.video, x / fps) for x in (a + max(2, n // 6), a - 1, a + n + 1))
        W = reference.SIG_W
        left = [i for i in range(len(mid_f)) if i % W < W // 5]
        right = [i for i in range(len(mid_f)) if i % W > W * 4 // 5]
        d = lambda a, b, idx: sum(abs(a[i] - b[i]) for i in idx) / len(idx)  # noqa: E731
        self.assertLess(d(mid_f, new, left), d(mid_f, old, left))
        self.assertLess(d(mid_f, old, right), d(mid_f, new, right))

    def test_delivery_is_complete_and_the_project_is_editable(self):
        """DEL-1: the deliver folder, and an ejected Remotion project that loads this film."""
        self.assertEqual(main(["-w", str(self.ws.root), "deliver", "--drafts"]), 0)
        d = self.ws.root / "deliver"
        m = read_json(d / "manifest.json")
        paths = {f["path"] for f in m["files"]}
        for want in ("videos/promo-16x9-draft.mp4", "CREATIVE_DIRECTION.md", "storyboard.md", "timeline.json",
                     "TEST_REPORT.md", "validation.json", "remotion/", "PRODUCT_ANALYSIS.md", "THEME_ANALYSIS.md",
                     "THEME.json", "ASSET_INVENTORY.md", "SCREENSHOT_MANIFEST.json", "screenshots/web-reports.png"):
            self.assertIn(want, paths)
        video = next(f for f in m["files"] if f["path"].startswith("videos/"))
        import hashlib
        self.assertEqual(hashlib.sha256((d / video["path"]).read_bytes()).hexdigest(), video["sha256"])
        proj = d / "remotion"
        self.assertEqual(read_json(proj / "src" / "sample" / "render-config.json")["durationInFrames"],
                         self.rc["durationInFrames"])
        self.assertTrue((proj / "public" / "audio" / "master.wav").is_file())
        self.assertTrue((proj / "public" / "assets" / "captured" / "web" / "reports-desktop.png").is_file())
        self.assertTrue((proj / "public" / "fonts" / "product.ttf").is_file(), "the product's own font travels too")
        self.assertTrue(next(f for f in m["files"] if f["path"] == "screenshots/web-reports.png")["usedInFilm"])
        (proj / "node_modules").symlink_to(RENDERER_DIR / "node_modules")  # skip a second npm ci
        tsc = subprocess.run(["npx", "tsc", "--noEmit"], cwd=proj, capture_output=True, text=True)
        self.assertEqual(tsc.returncode, 0, tsc.stdout + tsc.stderr)
        comps = subprocess.run(["npx", "remotion", "compositions", "src/index.ts"], cwd=proj,
                               capture_output=True, text=True)
        self.assertEqual(comps.returncode, 0, comps.stderr[-2000:])
        for cid in ("Promo16x9", "Promo9x16", "Promo1x1", "PromoStorePortrait", "PromoStoreLandscape"):
            self.assertIn(cid, comps.stdout)
        self.assertIn(str(self.rc["durationInFrames"]), comps.stdout, "the film's own length is the default")

    def test_discovery_drove_the_film(self):
        """The real app was launched and captured, and the film shows its screen in its theme."""
        m = read_json(self.ws.screenshot_manifest)
        self.assertEqual(m["web"]["status"], "captured")
        shot = screenshots_by(m)["web-reports"]
        self.assertTrue(shot["approved"] and shot["source"] == "captured")
        sc = next(s for s in self.rc["scenes"] if s["kind"] == "screen")
        self.assertEqual(sc["shots"], ["web-reports"])
        self.assertEqual(sc["props"]["media"], "captured/web/reports-desktop.png")
        th = read_json(self.ws.theme)["promo"]
        self.assertEqual((self.rc["style"]["ground"], self.rc["style"]["accent"]), (th["ground"], th["accent"]))
        mid = (sc["from"] + sc["durationInFrames"] * 0.6) / self.rc["fps"]
        corner = mean_rgb(self.video, mid, (0, 0, 6, 4))
        self.assertGreater(min(corner), 0.75, f"the light product's film stays light (corner {corner})")
        self.assertTrue(has_colour(self.video, mid, "#1F8A70"), "the real screen's brand green is on screen")
        for name in ("PRODUCT_ANALYSIS.md", "THEME_ANALYSIS.md", "ASSET_INVENTORY.md"):
            self.assertTrue((self.ws.root / name).is_file())
        self.assertIn("web-reports", self.ws.direction.read_text())

    def test_rendering_is_deterministic(self):
        again = self.tmp / "again.mp4"
        cmd = ["npx", "remotion", "render", "src/index.ts", "Promo16x9", str(again),
               f"--props={self.ws.root / 'build' / 'render-props.json'}", f"--public-dir={self.ws.stage}",
               "--crf=28", "--scale=0.5", "--log=error"]
        subprocess.run(cmd, cwd=RENDERER_DIR, check=True, capture_output=True)
        for sec in (1.0, 4.0, 7.0, 10.0, 14.0):
            a, b = frame_luma(self.video, sec), frame_luma(again, sec)
            self.assertLess(reference._mad(a, b), 0.002, f"frame at {sec}s differs between identical renders")


@skip
class AudioModesRendered(unittest.TestCase):
    """E2E-AUD: the same film in voice-over and silent modes (effects-only is AutonomousFilm)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-e2e-aud-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _build(self, audio: str) -> tuple[Workspace, Path]:
        ws = product(self.tmp / audio, audio=audio)
        ws.timeline.write_text(json.dumps(films.COMPACT, indent=2))
        if audio == "voiceover" and not shutil.which("say"):
            voice_files(ws, 3)
        code = main(["-w", str(ws.root), "build", "--quality", "draft"])
        self.assertEqual(code, 0, ws.qa_report.read_text() if ws.qa_report.exists() else "no report")
        return ws, ws.out_dir / "promo-16x9-draft.mp4"

    def test_voiceover_plus_effects(self):
        ws, video = self._build("voiceover")
        p = probe(video)
        self.assertIsNotNone(p["audio"])
        m = read_json(ws.root / "build" / "audio-manifest.json")
        self.assertEqual({s["kind"] for s in m["sources"]}, {"sfx", "voice"})
        self.assertFalse(m["music"])
        vo = read_json(ws.vo_dir / "manifest.json")
        self.assertEqual(len(vo["lines"]), 3)
        val = read_json(ws.qa_dir / "validation.json")
        self.assertEqual(val["audioPolicy"]["mode"], "voiceover")

    def test_silent_has_no_audio_stream(self):
        ws, video = self._build("silent")
        self.assertIsNone(probe(video)["audio"], "a silent film carries no audio stream at all")
        self.assertFalse(ws.master_audio.exists())
        self.assertEqual(read_json(ws.vo_dir / "manifest.json")["lines"], [])
        self.assertEqual(read_json(ws.qa_dir / "validation.json")["result"], "PASS")


@skip
class ReferenceFilm(unittest.TestCase):
    """E2E-B: synthetic reference → `promo watch` (the installed watch skill when present,
    with --no-whisper) → measured breakdown → CREATIVE_DIRECTION.md → storyboard → film →
    QA, including the check that the reference's transitions are visible in the film."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="promo-e2e-b-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)  # runs even if setUpClass fails
        cls.ref = cls.tmp / "reference.mp4"
        helpers.make_reference(cls.ref, "slow")
        cls.ws = ws = product(cls.tmp, audio="effects", reference_arg=str(cls.ref), web=True)
        w = ["-w", str(ws.root)]
        cls.watch_code = main(w + ["watch", "--no-whisper"])
        assert main(w + ["direction"]) == 0
        bd = direction.load_breakdown(ws)
        ws.direction.write_text(fill_direction(ws.direction.read_text(), bd))
        cls.direction_code = main(w + ["check", "direction"])
        assert main(w + ["storyboard"]) == 0
        write_json(ws.timeline, fill_timeline(read_json(ws.timeline)))
        cls.timeline_code = main(w + ["check", "timeline"])
        cls.code = main(w + ["build", "--quality", "draft"])
        cls.video = ws.out_dir / "promo-16x9-draft.mp4"

    def test_each_stage_passes(self):
        self.assertEqual((self.watch_code, self.direction_code, self.timeline_code), (0, 0, 0))
        self.assertEqual(self.code, 0, self.ws.qa_report.read_text() if self.ws.qa_report.exists() else "no report")
        ev = read_json(self.ws.evidence)
        # Whichever path ran is stated: the skill, the skill without its (ffmpeg-broken) frame
        # extraction, or promo's analyzer alone when the skill is not installed.
        self.assertRegex(ev["watch"]["note"], r"^watch skill( not installed| frame extraction failed|$)")

    def test_film_follows_the_reference(self):
        bd = direction.load_breakdown(self.ws)
        rc = read_json(self.ws.render_config)
        self.assertAlmostEqual(rc["duration"], bd["metadata"]["duration"], delta=0.05)
        val = read_json(self.ws.qa_dir / "validation.json")
        rows = val["reference"]
        self.assertEqual([r["measured"] for r in rows], ["dissolve", "wipe-left", "dip-black"])
        self.assertTrue(all(r["ok"] for r in rows), rows)
        self.assertEqual([r["observed"] for r in rows][1:], ["wipe-left", "dip-black"])

    def test_the_product_theme_and_real_screens_carry_the_reference_structure(self):
        """Reference: navy/orange/green/grey colour fields. Product: light, brand green. The film keeps
        the reference's transitions and the product's look and screens."""
        rc = read_json(self.ws.render_config)
        th = read_json(self.ws.theme)
        self.assertEqual(th["motion"]["source"], "reference/motion-spec.json")
        self.assertEqual((rc["style"]["ground"], rc["style"]["accent"]), (th["promo"]["ground"], th["promo"]["accent"]))
        screens = [s for s in rc["scenes"] if s.get("shots")]
        self.assertTrue(screens, "the storyboard put real captured screens into reference scenes")
        for s in screens:
            self.assertTrue(all(x.startswith("web-") for x in s["shots"]))
        self.assertEqual([s["transition"]["type"] for s in rc["scenes"][1:]], ["fade", "wipe", "dip"])
        t = (screens[0]["from"] + screens[0]["durationInFrames"] * 0.6) / rc["fps"]
        self.assertGreater(min(mean_rgb(self.video, t, (0, 0, 6, 4))), 0.75, "light product, light film")
        self.assertTrue(has_colour(self.video, t, "#1F8A70"))
        self.assertIn("SCREENSHOT MAPPING", self.ws.direction.read_text())

    def test_blind_analysis_of_the_film_recovers_the_reference_structure(self):
        """Analyse the finished film with no plan, as if it were a reference.

        Guaranteed: the strong dip is recovered, every detected transition starts inside a
        reference transition window (it may run on while the incoming scene animates in), and a
        detected wipe or dip has the reference's type. Not guaranteed blind: this wipe on sparse, dark frames changes
        ~0.003/frame against a ~0.002 adaptive threshold, so whether a blind pass catches it
        varies with encoding. The planned-window check in QA recovers it every time
        (test_film_follows_the_reference)."""
        out = reference.analyze(self.video, self.tmp / "film-analysis")
        windows = [(t["type"], t["start"], t["end"]) for t in direction.load_breakdown(self.ws)["transitions"]]
        slack = 2 / 30
        got = [(t["type"], t["start"], t["end"]) for t in out["transitions"]]
        self.assertIn("dip-black", [g[0] for g in got])
        for kind, a, b in got:
            inside = [w for w in windows if w[1] - slack <= a <= w[2] + slack]
            self.assertTrue(inside, f"{kind} starting at {a}s is outside every reference transition window")
            if kind.startswith("wipe-"):
                self.assertEqual(kind, inside[0][0])
            if kind == "dip-black":
                self.assertEqual(inside[0][0], "dip-black")


@skip
class StoreFormats(unittest.TestCase):
    """RND-2: exact App Store sizes and the vertical master, rendered and probed."""

    def test_exact_sizes(self):
        tmp = Path(tempfile.mkdtemp(prefix="promo-fmt-"))
        try:
            ws = product(tmp, audio="silent", formats=("store-portrait", "store-landscape", "9:16"), runtime="5-10")
            short = json.loads(json.dumps(films.COMPACT))
            short["scenes"] = [short["scenes"][2], short["scenes"][4]]  # the device scene + lockup
            short["scenes"][0].pop("transition")
            ws.timeline.write_text(json.dumps(short, indent=2))
            self.assertEqual(main(["-w", str(ws.root), "build", "--quality", "draft"]), 0, ws.qa_report.read_text())
            want = {"store-portrait": (886, 1920), "store-landscape": (1920, 886), "9:16": (540, 960)}
            for aspect, (w, h) in want.items():
                video = ws.out_dir / f"promo-{aspect.replace(':', 'x')}-draft.mp4"
                p = probe(video)
                self.assertEqual((p["w"], p["h"]), (w, h), aspect)
                self.assertIsNone(p["audio"], "silent mode")
                # The device never touches the frame edges while the camera pushes in: edge pixels stay
                # the film's ground colour (light here: the product's theme is light).
                g = read_json(ws.render_config)["style"]["ground"].lstrip("#")
                ground = round(0.299 * int(g[0:2], 16) + 0.587 * int(g[2:4], 16) + 0.114 * int(g[4:6], 16))
                for t in (0.6, 1.8, 3.2):
                    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1",
                                          "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
                    self.assertEqual(len(raw), w * h)
                    edge = max(max(abs(raw[y * w + x] - ground) for x in (0, 1, 2, w - 3, w - 2, w - 1)) for y in range(0, h, 4))
                    self.assertLess(edge, 45, f"{aspect} at {t}s: content touches the frame edge ({edge})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(os.environ.get("PROMO_MOBILE") == "1" and shutil.which("flutter") and shutil.which("xcrun")
                     and helpers.has_ffmpeg(), "set PROMO_MOBILE=1 (needs Flutter, Xcode simulators and ffmpeg; ~2 min)")
class RealSimulator(unittest.TestCase):
    """DISC-8: a real Flutter iOS app, built and launched on promo's own simulator, every
    route reached and captured, the simulator removed afterwards."""

    def test_real_app_screens_are_captured(self):
        tmp = Path(tempfile.mkdtemp(prefix="promo-sim-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        root = helpers.make_flutter_product(tmp / "tallyboard")
        ws = Workspace.at(root / "promo")
        assert main(["-w", str(ws.root), "init", "--product", str(root), "--name", "Tallyboard"]) == 0
        assert main(["-w", str(ws.root), "discover"]) == 0
        m = read_json(ws.screenshot_manifest)
        self.assertEqual(m["mobile"]["status"], "captured", m["mobile"])
        shots = {s["id"]: s for s in m["screenshots"] if s["platform"] == "ios"}
        self.assertEqual(set(shots), {"ios-launch", "ios-history", "ios-result"})
        for s in shots.values():
            self.assertEqual((s["width"], s["height"]), (1206, 2622))
            self.assertTrue(s["approved"], s["reason"])
        structures = [reference._z(reference._luma(reference._frame_at(ws.root / s["path"], 0, 64, 36))) for s in shots.values()]
        for i in range(len(structures)):
            for j in range(i + 1, len(structures)):
                self.assertGreater(reference._mad(structures[i], structures[j]), 0.10, "three distinct real screens")
        agree = {c["role"]: c["agrees"] for c in read_json(ws.theme)["original"]["corroboration"]}
        self.assertEqual(agree, {"background": True, "primary": True})
        sims = subprocess.run(["xcrun", "simctl", "list", "devices"], capture_output=True, text=True).stdout
        self.assertNotIn("PromoVideo Capture", sims, "promo removes the simulator it created")
