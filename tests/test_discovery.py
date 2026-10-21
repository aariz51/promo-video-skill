"""PRODUCT_THEME_DISCOVERY: codebase, theme, live web/mobile inspection, screenshot selection,
and how both production modes consume them.

The web tests launch a real local fixture app (Node) and capture it with headless Chrome. The
mobile tests mock the device toolchain (simctl / adb / flutter / xcodebuild); a real simulator
run lives in test_render.py behind PROMO_MOBILE=1.
"""
from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
from helpers import Env, has_ffmpeg, png  # noqa: E402

from promo_engine import capture, discovery, direction, mobile, render, screenshots, theme, timeline
from promo_engine.cli import main
from promo_engine.config import Workspace, init_workspace
from promo_engine.util import PromoError, read_json, write_json


def have_chrome() -> bool:
    try:
        capture.find_chrome()
        return True
    except PromoError:
        return False


WEB_READY = bool(shutil.which("node")) and have_chrome() and has_ffmpeg()
web_only = unittest.skipUnless(WEB_READY, "needs node, Chrome and ffmpeg")
ARTIFACTS = ("PRODUCT_ANALYSIS.md", "THEME_ANALYSIS.md", "THEME.json", "ASSET_INVENTORY.md", "SCREENSHOT_MANIFEST.json")


def web_workspace(tmp: Path, *, broken: bool = False) -> tuple[Path, Workspace, int]:
    port = helpers.free_port()
    prod = helpers.make_web_product(tmp / "tallyboard", port, broken=broken)
    ws = Workspace.at(prod / "promo")
    init_workspace(ws, product_root=prod, name="Tallyboard")
    return prod, ws, port


def all_text(root: Path) -> str:
    return "\n".join(p.read_text(errors="ignore") for p in root.rglob("*")
                     if p.is_file() and p.suffix in (".md", ".json", ".txt", ".log", ""))


# ── A. workflow integration ─────────────────────────────────────────────────────────

class Workflow(unittest.TestCase):
    def setUp(self):
        self.env = Env()

    def tearDown(self):
        self.env.close()

    def test_neither_mode_builds_a_storyboard_before_discovery(self):
        self.env.ws.brief.write_text(helpers.BRIEF)
        self.env.ws.timeline.write_text(json.dumps(helpers.timeline()))
        with self.assertRaises(PromoError) as cm:
            timeline.compile_timeline(self.env.ws)  # Mode A
        self.assertIn("promo discover", cm.exception.hint)
        self.assertEqual(main(["-w", str(self.env.ws.root), "check", "timeline"]), 2)
        main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product), "--reference",
              "https://vimeo.com/76979871"])  # Mode B
        with self.assertRaises(PromoError):
            direction.storyboard(self.env.ws)
        helpers.discover_offline(self.env.ws)
        self.assertTrue(discovery.done(self.env.ws))

    def test_discovery_runs_in_both_modes_and_writes_into_the_workspace(self):
        before = sorted(p.relative_to(self.env.product) for p in self.env.product.rglob("*") if "promo" not in p.parts)
        for ref in ("none", "https://vimeo.com/76979871"):
            main(["-w", str(self.env.ws.root), "init", "--product", str(self.env.product), "--reference", ref])
            res = helpers.discover_offline(self.env.ws)
            self.assertEqual(res["manifest"]["stage"], discovery.STAGE)
            for name in ARTIFACTS:
                self.assertTrue((self.env.ws.root / name).is_file(), name)
        after = sorted(p.relative_to(self.env.product) for p in self.env.product.rglob("*") if "promo" not in p.parts)
        self.assertEqual(before, after, "the product itself is inspected, never modified")
        self.assertIn("assets/captured/", (self.env.ws.root / ".gitignore").read_text())
        self.assertEqual(res["manifest"]["web"]["status"], "skipped", "an unlaunched app is never called inspected")

    def test_the_skill_repository_is_never_mistaken_for_the_product(self):
        tmp = Path(tempfile.mkdtemp(prefix="promo-self-"))
        try:
            ws = Workspace.at(tmp / "promo")
            init_workspace(ws, product_root=discovery.SKILL_REPO)
            with self.assertRaises(PromoError) as cm:
                discovery.check_target(ws)
            self.assertIn("skill itself", str(cm.exception))
            cfg = read_json(ws.config_path)
            cfg["product"]["selfPromo"] = True
            write_json(ws.config_path, cfg)
            self.assertEqual(discovery.check_target(ws), discovery.SKILL_REPO)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_genuine_screenshots_is_stated_not_hidden(self):
        bare = self.env.tmp / "bare"
        (bare / "src").mkdir(parents=True)
        (bare / "src" / "main.py").write_text("print('hi')\n")
        ws = Workspace.at(bare / "promo")
        init_workspace(ws, product_root=bare, name="Bare")
        helpers.discover_offline(ws)
        self.assertIn("No genuine product screenshots are available", ws.product_analysis.read_text())
        th = read_json(ws.theme)
        self.assertEqual(th["original"]["modes"], {})
        self.assertIn("no brand colour found", " ".join(th["promo"]["notes"]))
        self.assertIn("unknown", ws.theme_analysis.read_text())


# ── B. live web app ─────────────────────────────────────────────────────────────────

@web_only
class WebApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="promo-web-"))
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.prod, cls.ws, cls.port = web_workspace(cls.tmp)
        cls.res = discovery.run(cls.ws)
        cls.m = cls.res["manifest"]

    def test_the_real_app_launches_and_its_routes_are_inspected(self):
        web = self.m["web"]
        self.assertEqual(web["status"], "captured")
        self.assertIn("npm run dev", web["launch"]["how"])
        rows = {r["route"]: r for r in web["routes"]}
        self.assertEqual(rows["/"]["finding"], "renders")
        self.assertEqual(rows["/reports"]["finding"], "renders")
        self.assertIn("Start a report", rows["/"]["ctas"])
        self.assertIn("Tallyboard", rows["/reports"]["title"])
        self.assertEqual(rows["/team"]["finding"], "unavailable (HTTP 404)")
        self.assertIn("requires authentication", rows["/admin"]["finding"])
        self.assertFalse((self.ws.captured / "web" / "team-desktop.png").exists(), "unavailable routes are not fabricated")
        self.assertFalse((self.ws.captured / "web" / "admin-desktop.png").exists())

    def test_screenshots_are_real_files_listed_in_the_manifest(self):
        captured = [s for s in self.m["screenshots"] if s["source"] == "captured"]
        self.assertGreaterEqual(len(captured), 2)
        for s in captured:
            f = self.ws.root / s["path"]
            self.assertTrue(f.is_file() and f.stat().st_size > 10_000, s["id"])
            facts = screenshots.image_facts(f)
            self.assertEqual((facts["width"], facts["height"]), (1920, 1080))
            for key in ("id", "path", "product", "platform", "screen", "route", "capturedAt", "width", "height",
                        "source", "feature", "state", "limitations", "approved", "reason"):
                self.assertIn(key, s)
            self.assertEqual((s["platform"], s["product"]), ("web", "Tallyboard"))
        by = {s["id"]: s for s in captured}
        self.assertEqual(by["web-reports"]["feature"], "$2,418.60 this month", "the screen's own heading names it")

    def test_selection_prefers_the_valuable_screens(self):
        by = {s["id"]: s for s in self.m["screenshots"]}
        self.assertTrue(by["web-home"]["selected"] and by["web-reports"]["selected"])
        self.assertFalse(by["web-settings"]["selected"])
        self.assertIn("account data", by["web-settings"]["reason"])
        self.assertFalse(by["supplied-dashboard"]["selected"], "a 320 px placeholder is too small for a film")
        self.assertIn("too small", by["supplied-dashboard"]["reason"])

    def test_theme_comes_from_tokens_and_is_corroborated_by_the_real_screens(self):
        th = self.res["theme"]
        o = th["original"]
        self.assertEqual(o["defaultMode"], "light")
        self.assertEqual(o["modes"]["light"]["primary"]["value"], "#1F8A70")
        self.assertEqual(o["modes"]["dark"]["background"]["value"], "#0F1412")
        self.assertTrue(o["hasDarkMode"])
        for m in o["modes"].values():
            for role in m.values():
                self.assertRegex(role["value"], r"^#[0-9A-F]{6}$")
        agree = {c["role"]: c["agrees"] for c in o["corroboration"]}
        self.assertEqual(agree, {"background": True, "primary": True})
        self.assertEqual((th["promo"]["ground"], th["promo"]["accent"], th["promo"]["dark"]), ("#F7F5F0", "#1F8A70", False))
        self.assertEqual(th["promo"]["fontFile"], "public/fonts/Inter.ttf")

    def test_reports_carry_no_secrets_or_private_config(self):
        text = all_text(self.ws.root)
        self.assertNotIn("do-not-read-me", text)  # the fixture's .env
        self.assertNotIn("sk-fake-should-never-be-read", text)
        self.assertNotIn("SECRET_TOKEN", text)


@web_only
class WebFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-webfail-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_failed_launch_is_blocked_with_a_safe_diagnostic(self):
        prod, ws, _ = web_workspace(self.tmp, broken=True)
        res = discovery.run(ws, startup_timeout=8)
        web = res["manifest"]["web"]
        self.assertEqual((web["status"], web["stage"]), ("blocked", "dev server startup"))
        self.assertTrue(any("Cannot find module" in x for x in web["limitations"]), web["limitations"])
        self.assertFalse(list(ws.captured.glob("web/*.png")))
        self.assertNotIn("hunter2", all_text(ws.root), "the credential the server printed is never repeated")
        self.assertIn("launch was blocked", ws.product_analysis.read_text())

    def test_a_port_held_by_another_app_is_neither_used_nor_stopped(self):
        prod, ws, port = web_workspace(self.tmp)
        other = self.tmp / "other"
        other.mkdir()
        (other / "index.html").write_text("<h1>Some other project</h1>")
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(other), **k)  # noqa: E731
        srv = socketserver.TCPServer(("127.0.0.1", port), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            res = discovery.run(ws)
            web = res["manifest"]["web"]
            self.assertEqual(web["status"], "blocked")
            self.assertIn("does not name", " ".join(web["limitations"]))
            self.assertEqual(capture.http_probe(f"http://localhost:{port}/")["status"], 200, "still running")
        finally:
            srv.shutdown()
            srv.server_close()

    def test_an_already_running_copy_of_the_product_is_reused(self):
        prod, ws, port = web_workspace(self.tmp)
        proc = subprocess.Popen(["node", "server.js", str(port)], cwd=prod, stdout=subprocess.DEVNULL)
        try:
            capture.wait_for(f"http://localhost:{port}/", 20)
            res = discovery.run(ws)
            self.assertIn("reused", res["manifest"]["web"]["launch"]["how"])
            self.assertEqual(res["manifest"]["web"]["status"], "captured")
        finally:
            proc.terminate()
            proc.wait(10)

    def test_scripts_that_touch_data_are_never_run(self):
        for script in ("prisma migrate reset --force && next dev", "npm run db:push && vite", "vercel --prod"):
            with self.assertRaises(PromoError):
                capture.check_launch_command({"command": "npm run dev", "script": script})
        with self.assertRaises(PromoError):
            capture.check_launch_command({"command": "npm run seed", "script": "node seed.js"})
        capture.check_launch_command({"command": "npm run dev", "script": "next dev --port 3000"})


class DomReading(unittest.TestCase):
    def test_runtime_errors_and_blank_pages_are_recognised(self):
        err = capture.read_dom("<html><body><h1>Unhandled Runtime Error</h1><p>TypeError: x is undefined</p></body></html>")
        self.assertTrue(err["errors"])
        blank = capture.read_dom("<html><head><title>App</title></head><body><div id='root'></div></body></html>")
        self.assertLess(blank["textLength"], 20)
        ok = capture.read_dom("<html><head><title>Reports · Tallyboard</title><script>var a</script></head><body>"
                              "<button>Export CSV</button><img src='/logo.png'></body></html>")
        self.assertEqual((ok["title"], ok["ctas"], ok["assets"], ok["errors"]),
                         ("Reports · Tallyboard", ["Export CSV"], ["/logo.png"], []))


# ── C. mobile (mocked device toolchain) ─────────────────────────────────────────────

SIMS = {"devices": {"com.apple.CoreSimulator.SimRuntime.iOS-26-0": [
    {"udid": "OTHER-BOOTED", "name": "Someone else's QA iPhone", "state": "Booted"},
    {"udid": "SPARE", "name": "iPhone 17", "state": "Shutdown"}]}}


class FakeDevices:
    """simctl / flutter / adb / xcodebuild stand-in. Records every command; `fail` names a step."""

    def __init__(self, tmp: Path, *, ios=True, adb_devices="", emulator=None, fail=None, own=False):
        self.tmp, self.calls, self.fail = tmp, [], fail
        self.route, self.same_screen = "/", False
        self.ios, self.adb_devices, self.emulator = ios, adb_devices, emulator
        self.sims = json.loads(json.dumps(SIMS))
        if own:
            self.sims["devices"]["com.apple.CoreSimulator.SimRuntime.iOS-26-0"].append(
                {"udid": "PROMO-OWN", "name": mobile.SIM_NAME, "state": "Shutdown"})

    def __call__(self, cmd, *, cwd=None, timeout=600, binary=False):
        self.calls.append(cmd)
        ok = lambda out="": subprocess.CompletedProcess(cmd, 0, out, "")  # noqa: E731
        bad = lambda err: subprocess.CompletedProcess(cmd, 1, b"" if binary else "", err)  # noqa: E731
        c = " ".join(map(str, cmd))
        if cmd[0] == "xcrun" and not self.ios:
            return subprocess.CompletedProcess(cmd, 127, "", "xcrun: command not found")
        if c.startswith("xcrun simctl list devices"):
            return ok(json.dumps(self.sims))
        if c.startswith("xcrun simctl list devicetypes"):
            return ok(json.dumps({"devicetypes": [{"name": "iPhone 17", "identifier": "com.apple.dt.iPhone-17"}]}))
        if c.startswith("xcrun simctl list runtimes"):
            return ok(json.dumps({"runtimes": [{"identifier": "com.apple.CoreSimulator.SimRuntime.iOS-26-0", "platform": "iOS"}]}))
        if c.startswith("xcrun simctl create"):
            return ok("PROMO-NEW\n")
        if c.startswith("flutter build"):
            if self.fail == "build":
                return bad("Error: Xcode build failed: Signing for 'Runner' requires a development team.")
            app = Path(cwd) / "build" / "ios" / "iphonesimulator" / "Runner.app"
            app.mkdir(parents=True, exist_ok=True)
            return ok()
        if cmd[:2] == ["plutil", "-extract"]:
            return ok("com.example.tallyboard\n")
        if c.startswith("xcrun simctl launch") and self.fail == "launch":
            return bad("Unable to launch com.example.tallyboard")
        if c.startswith("xcrun simctl launch"):
            arg = next((a for a in cmd if str(a).startswith("--route=")), "--route=/")
            self.route = arg.split("=", 1)[1]
            return ok("com.example.tallyboard: 4242\n")
        if c.startswith("xcrun simctl io"):
            # Each screen has its own layout (band height), unless the app ignores navigation.
            band = {"/": 0.1, "/history": 0.35, "/result": 0.6}.get("/" if self.same_screen else self.route, 0.2)
            png(Path(cmd[-1]), 1179, 2556, (32, 120, 96), band=band)
            return ok()
        if cmd[0] == "adb" and cmd[1:] == ["devices"]:
            return ok("List of devices attached\n" + self.adb_devices)
        if cmd[0] == "emulator":
            return subprocess.CompletedProcess(cmd, 127, "", "") if self.emulator is None else ok(self.emulator)
        return ok()


def flutter_app(root: Path, *, deep_links=True) -> Path:
    (root / "lib").mkdir(parents=True)
    (root / "ios" / "Runner").mkdir(parents=True)
    (root / "android" / "app").mkdir(parents=True)
    (root / "pubspec.yaml").write_text("name: tallyboard\nflutter:\n  uses-material-design: true\n"
                                       "  # fonts:\n  #   - family: Schyler\n  fonts:\n"
                                       "    - family: Nunito\n      fonts:\n        - asset: fonts/Nunito.ttf\n")
    (root / "lib" / "main.dart").write_text(
        "final theme = ThemeData(brightness: Brightness.light, colorScheme: ColorScheme.light(\n"
        "  primary: const Color(0xFF1F8A70), surface: Color(0xFFFFFFFF)), scaffoldBackgroundColor: Color(0xFFF7F5F0));\n"
        "final darkTheme = ThemeData(brightness: Brightness.dark, colorScheme: ColorScheme.dark(\n"
        "  primary: Color(0xFF3FBF9B), surface: Color(0xFF18201D)), scaffoldBackgroundColor: Color(0xFF0F1412));\n"
        "final routes = {'/': (c) => Home(), '/history': (c) => History(), '/result': (c) => Result()};\n")
    plist = "<plist><dict>"
    if deep_links:
        plist += "<key>CFBundleURLTypes</key><array><dict><key>CFBundleURLSchemes</key><array><string>tallyboard</string></array></dict></array>"
    (root / "ios" / "Runner" / "Info.plist").write_text(plist + "</dict></plist>")
    (root / "android" / "app" / "build.gradle").write_text('android { defaultConfig { applicationId "com.example.tallyboard" } }\n')
    return root


class MobileApp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-mobile-"))
        self.root = flutter_app(self.tmp / "app")
        self.ws = Workspace.at(self.root / "promo")
        init_workspace(self.ws, product_root=self.root, name="Tallyboard")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_platforms_are_detected_from_the_project(self):
        self.assertEqual(mobile.detect_platforms(self.root)[0]["platform"], "flutter")
        rn = self.tmp / "rn"
        rn.mkdir()
        (rn / "package.json").write_text(json.dumps({"dependencies": {"react-native": "0.80.0"}}))
        self.assertEqual(mobile.detect_platforms(rn)[0]["platform"], "react-native")
        native = self.tmp / "native"
        (native / "Tally.xcodeproj").mkdir(parents=True)
        self.assertEqual(mobile.detect_platforms(native)[0]["platform"], "ios")

    def test_a_dedicated_simulator_is_used_and_cleaned_up(self):
        dev = FakeDevices(self.tmp)
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root),
                                    run=dev, settle=0)
        self.assertEqual(rep["status"], "captured")
        flat = [" ".join(map(str, c)) for c in dev.calls]
        self.assertTrue(any(c.startswith(f"xcrun simctl create {mobile.SIM_NAME}") for c in flat))
        self.assertFalse(any("OTHER-BOOTED" in c for c in flat), "someone else's booted simulator is never touched")
        self.assertIn("xcrun simctl delete PROMO-NEW", flat, "the simulator promo created is deleted")
        self.assertEqual([s["screen"] for s in rep["shots"]], ["launch", "history", "result"])
        # Routes are reached with Flutter's --route launch argument, never `openurl` (iOS would
        # show an "Open in …?" confirmation over the previous screen).
        self.assertTrue(any("launch PROMO-NEW com.example.tallyboard --route=/history" in c for c in flat))
        self.assertFalse(any("openurl" in c for c in flat))
        self.assertEqual(rep["launch"]["bundleId"], "com.example.tallyboard")
        self.assertTrue(all("reached by launch argument" in s["finding"] for s in rep["screens"][1:]))

    def test_promos_own_simulator_is_reused_and_kept(self):
        dev = FakeDevices(self.tmp, own=True)
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root),
                                    run=dev, settle=0)
        flat = [" ".join(map(str, c)) for c in dev.calls]
        self.assertEqual(rep["device"]["id"], "PROMO-OWN")
        self.assertFalse(any(c.startswith("xcrun simctl create") or c.startswith("xcrun simctl delete") for c in flat))

    def test_no_device_is_an_accurate_blocked_status_not_a_launch(self):
        dev = FakeDevices(self.tmp, ios=False, emulator=None)
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root), run=dev)
        self.assertEqual((rep["status"], rep["stage"], rep["launch"]), ("blocked", "device discovery", None))
        self.assertIn("iOS: no iOS Simulator", " ".join(rep["limitations"]), "every platform tried says why it failed")
        self.assertIn("Android: no Android emulator or device: the Android emulator is not installed", " ".join(rep["limitations"]))
        dev = FakeDevices(self.tmp, ios=False, emulator="Pixel_8_API_35\n")
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root), run=dev)
        self.assertIn("none is running", " ".join(rep["limitations"]))

    def test_build_and_launch_failures_are_reported_at_their_stage(self):
        for step, stage, needle in (("build", "build", "development team"), ("launch", "install/launch", "Unable to launch")):
            dev = FakeDevices(self.tmp, fail=step)
            rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root),
                                        run=dev, settle=0)
            self.assertEqual((rep["status"], rep["stage"]), ("blocked", stage))
            self.assertIn(needle, rep["limitations"][0])
            self.assertFalse(rep["shots"])

    def test_a_route_that_lands_on_the_same_screen_is_not_claimed(self):
        dev = FakeDevices(self.tmp)
        dev.same_screen = True
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root),
                                    run=dev, settle=0)
        self.assertEqual([s["screen"] for s in rep["shots"]], ["launch"])
        self.assertTrue(all("did not navigate" in s["finding"] for s in rep["screens"][1:]), rep["screens"])
        self.assertFalse((self.ws.captured / "mobile" / "ios-history.png").exists())

    def test_native_ios_custom_scheme_links_are_not_followed_unattended(self):
        native = self.tmp / "native"
        (native / "Tally.xcodeproj").mkdir(parents=True)
        (native / "lib").mkdir()
        (native / "lib" / "routes.dart").write_text("GoRoute(path: '/history')")
        (native / "Tally").mkdir()
        (native / "Tally" / "Info.plist").write_text("<key>CFBundleURLSchemes</key><array><string>tally</string></array>")
        scheme, routes = mobile.deep_links(native, "ios")
        self.assertEqual((scheme, routes), ("tally", ["/history"]))

    def test_flutter_routes_need_no_url_scheme(self):
        shutil.rmtree(self.root)
        flutter_app(self.root, deep_links=False)
        rep = mobile.inspect_mobile(self.ws, product_root=self.root, platforms=mobile.detect_platforms(self.root),
                                    run=FakeDevices(self.tmp), settle=0)
        self.assertEqual([s["screen"] for s in rep["shots"]], ["launch", "history", "result"])

    def test_without_a_way_to_navigate_only_the_launch_screen_is_claimed(self):
        app = self.tmp / "droid"
        (app / "app").mkdir(parents=True)
        (app / "app" / "build.gradle").write_text('plugins { id "com.android.application" }\n'
                                                   'android { defaultConfig { applicationId "com.example.droid" } }\n')
        (app / "lib").mkdir()
        (app / "lib" / "routes.dart").write_text("GoRoute(path: '/history')")
        ws = Workspace.at(app / "promo")
        init_workspace(ws, product_root=app, name="Droid")
        dev = FakeDevices(self.tmp, ios=False, adb_devices="emulator-5554\tdevice\n")
        orig = dev.__call__

        def run(cmd, **kw):
            if cmd[:3] == ["adb", "-s", "emulator-5554"] and "screencap" in cmd:
                p = self.tmp / "droid.png"
                png(p, 1080, 2400, (32, 120, 96))
                return subprocess.CompletedProcess(cmd, 0, p.read_bytes(), b"")
            return orig(cmd, **kw)
        rep = mobile.inspect_mobile(ws, product_root=app, platforms=mobile.detect_platforms(app), run=run, settle=0)
        self.assertEqual([s["screen"] for s in rep["shots"]], ["launch"])
        self.assertIn("no URL scheme is declared", " ".join(rep["limitations"]))

    @unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
    def test_mobile_captures_enter_the_manifest_and_theme(self):
        res = discovery.run(self.ws, runner=FakeDevices(self.tmp), launch=True)
        m = res["manifest"]
        ios = [s for s in m["screenshots"] if s["platform"] == "ios"]
        self.assertEqual({s["id"] for s in ios}, {"ios-launch", "ios-history", "ios-result"})
        self.assertTrue(all(s["source"] == "captured" and (self.ws.root / s["path"]).is_file() for s in ios))
        self.assertEqual(m["mobile"]["status"], "captured")
        pal = res["theme"]["original"]["modes"]
        self.assertEqual(pal["light"]["primary"]["value"], "#1F8A70")
        self.assertEqual(pal["dark"]["background"]["value"], "#0F1412")
        self.assertEqual([f["family"] for f in res["theme"]["typography"]["families"]], ["Nunito"],
                         "a commented-out font in pubspec.yaml is not the product's font")
        self.assertEqual({s["id"]: s["feature"] for s in ios}["ios-history"], "history screen")


# ── D. theme discovery across stacks ────────────────────────────────────────────────

class ThemeStacks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="promo-theme-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ios_colorsets_and_android_resources(self):
        cs = self.tmp / "Tally" / "Assets.xcassets" / "Brand.colorset"
        cs.mkdir(parents=True)
        (cs / "Contents.json").write_text(json.dumps({"colors": [
            {"color": {"components": {"red": "0x1F", "green": "0x8A", "blue": "0x70", "alpha": "1.000"}}},
            {"appearances": [{"appearance": "luminosity", "value": "dark"}],
             "color": {"components": {"red": "0.247", "green": "0.749", "blue": "0.608", "alpha": "1.000"}}}]}))
        for night, bg in (("values", "#FFF7F5F0"), ("values-night", "#0F1412")):
            d = self.tmp / "app" / "src" / "main" / "res" / night
            d.mkdir(parents=True)
            (d / "colors.xml").write_text(f'<resources><color name="background">{bg}</color></resources>')
        tokens = theme.collect_tokens(self.tmp)
        got = {(t["name"], t["mode"], t["value"]) for t in tokens}
        self.assertIn(("Brand", "light", "#1F8A70"), got)
        self.assertIn(("Brand", "dark", "#3FBF9B"), got)
        self.assertIn(("background", "light", "#F7F5F0"), got)
        self.assertIn(("background", "dark", "#0F1412"), got)

    def test_tailwind_and_shadcn_hsl_tokens(self):
        (self.tmp / "tailwind.config.js").write_text("module.exports = { theme: { extend: { colors: { brand: '#7C3AED' },"
                                                     " fontFamily: { sans: ['Satoshi', 'sans-serif'] } } } }")
        (self.tmp / "app.css").write_text(":root { --background: 0 0% 100%; --primary: 262.1 83.3% 57.8%; }\n"
                                          ".dark { --background: 224 71.4% 4.1%; }")
        th = theme.discover(self.tmp)
        self.assertEqual(th["original"]["modes"]["light"]["background"]["value"], "#FFFFFF")
        self.assertEqual(th["original"]["modes"]["dark"]["background"]["value"], "#030712")
        self.assertIn(th["original"]["modes"]["light"]["primary"]["value"], ("#7C3AED", "#7C3BED"))
        self.assertEqual(th["typography"]["families"][0]["family"], "Satoshi")
        self.assertIn("no font file", " ".join(th["promo"]["notes"]), "a font without a file is not faked")

    def test_low_contrast_text_is_fixed_for_video_and_said(self):
        (self.tmp / "a.css").write_text(":root { --background: #FFFFFF; --foreground: #CCCCCC; --primary: #FF5A1F; }")
        promo = theme.discover(self.tmp)["promo"]
        self.assertEqual(promo["ink"], "#111111")
        self.assertIn("below 4.5:1", " ".join(promo["notes"]))


# ── D/E. the theme and the screenshots drive the build, in both modes ───────────────

@unittest.skipUnless(has_ffmpeg(), "ffmpeg required")
class BuildConsumesDiscovery(unittest.TestCase):
    def setUp(self):
        self.env = Env().with_artifacts()
        ws = self.env.ws
        # Two genuine screens supplied by the user at film resolution, one duplicate, one illustration, one broken.
        self.a = png(self.env.tmp / "in" / "dashboard.png", 1920, 1080, (60, 140, 110))
        self.b = png(self.env.tmp / "in" / "reports-view.png", 1920, 1080, (40, 40, 60))
        self.c = self.env.tmp / "in" / "dashboard-copy.png"
        shutil.copy(self.a, self.c)
        bad = self.env.tmp / "in" / "broken.png"
        bad.write_text("not an image")
        png(ws.assets / "illustrations" / "flow.png", 1600, 900, (150, 100, 40))
        self.res = discovery.run(ws, launch=False, inspect_mobile=False, supplied=[self.a, self.b, self.c, bad])
        self.m = self.res["manifest"]

    def tearDown(self):
        self.env.close()

    def _tl(self, **scene_over) -> dict:
        tl = helpers.timeline()
        tl["scenes"][3]["props"]["media"] = "shot:supplied-dashboard"
        tl["scenes"][3].update(scene_over)
        return tl

    def test_selection_manifest(self):
        by = screenshots.by_id(self.m)
        self.assertTrue(by["supplied-dashboard"]["selected"])
        self.assertFalse(by["supplied-dashboard-copy"]["selected"])
        self.assertIn("near-duplicate", by["supplied-dashboard-copy"]["reason"])
        self.assertEqual(by["illustration-flow"]["source"], "illustration")
        self.assertFalse(by["illustration-flow"]["genuine"])
        self.assertFalse(by["illustration-flow"]["approved"])
        self.assertIn("broken.png", [r["path"] for r in self.m["rejected"]])
        for s in self.m["screenshots"]:
            if s["selected"]:
                self.assertTrue((self.env.ws.root / s["path"]).is_file())

    def test_screenshot_ids_flow_into_the_storyboard(self):
        write_json(self.env.ws.timeline, self._tl())
        rc, rep = timeline.compile_timeline(self.env.ws)
        self.assertTrue(rep.ok, rep.summary())
        scene = rc["scenes"][3]
        self.assertEqual(scene["shots"], ["supplied-dashboard"])
        self.assertEqual(scene["props"]["media"], "supplied/dashboard.png")
        self.assertIn("supplied-dashboard", self.env.ws.storyboard.read_text())
        self.assertIn("`supplied-dashboard`", self.env.ws.direction.read_text())

    def test_screenshot_misuse_is_rejected(self):
        cases = {"is not in SCREENSHOT_MANIFEST.json": self._tl(props={"media": "shot:web-nope"}),
                 "is not approved": self._tl(props={"media": "shot:supplied-dashboard-copy"}),
                 "is an illustration": self._tl(props={"media": "shot:illustration-flow"}),
                 "refer to screens by id": self._tl(props={"media": "captured/web/invented.png"})}
        for needle, tl in cases.items():
            rep = timeline.validate(tl, self.env.ws, self.env.ws.config(), {"C1": {}, "C2": {}, "C3": {}})
            self.assertIn(needle, rep.summary(), needle)
        ok = self._tl(props={"media": "shot:illustration-flow"}, illustrative=True)
        rep = timeline.validate(ok, self.env.ws, self.env.ws.config(), {"C1": {}, "C2": {}, "C3": {}})
        self.assertNotIn("illustration", rep.summary())

    def test_the_theme_is_the_films_style_and_the_font_is_staged(self):
        write_json(self.env.ws.timeline, self._tl())
        rc, rep = timeline.compile_timeline(self.env.ws)
        promo = read_json(self.env.ws.theme)["promo"]
        for k in ("ground", "ink", "accent"):
            self.assertEqual(rc["style"][k], promo[k], k)
        self.assertEqual((rc["style"]["ground"], rc["style"]["dark"]), ("#F7F5F0", False), "a light product stays light")
        self.assertEqual(rc["style"]["source"], "THEME.json")
        # A product font file reaches the renderer's public dir.
        th = read_json(self.env.ws.theme)
        th["promo"]["fontFile"] = "public/logo.png"  # any product file stands in for the font in this check
        write_json(self.env.ws.theme, th)
        rc, _ = timeline.compile_timeline(self.env.ws)
        self.assertEqual(rc["style"]["fontFile"], "fonts/product.png")
        with self.assertRaises(PromoError):  # no audio master yet; the font is staged before that check
            render.stage(self.env.ws, rc)
        self.assertTrue((self.env.ws.stage / rc["style"]["fontFile"]).is_file())

    def test_branding_is_kept_unless_a_departure_is_declared(self):
        tl = self._tl()
        tl["style"] = {"accent": "#FF00AA"}
        msg = timeline.validate(tl, self.env.ws, self.env.ws.config(), {"C1": {}, "C2": {}, "C3": {}}).summary()
        self.assertIn("differs from the product's #1F8A70", msg)
        tl["style"] = {"preset": "graphite"}
        msg = timeline.validate(tl, self.env.ws, self.env.ws.config(), {"C1": {}, "C2": {}, "C3": {}}).summary()
        self.assertIn("turns the product's light interface dark", msg)
        tl["style"] = {"preset": "graphite", "deviation": "night launch event, approved by the client"}
        msg = timeline.validate(tl, self.env.ws, self.env.ws.config(), {"C1": {}, "C2": {}, "C3": {}}).summary()
        self.assertNotIn("timeline.style", msg)


if __name__ == "__main__":
    unittest.main()
