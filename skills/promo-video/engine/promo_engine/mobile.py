"""Live inspection of a mobile product: detect the stack, find a device, build, launch, capture.

Supported automatically:
  flutter → iOS Simulator   `flutter build ios --simulator`, `simctl install/launch`
  ios     → iOS Simulator   `xcodebuild` (first scheme) into the workspace's derived data
  android → emulator/device `./gradlew installDebug`, `adb … monkey` to launch
React Native / Expo need a Metro server and are reported as not automated.

Devices: promo never borrows a simulator someone else has booted. It uses (or creates, then
deletes) its own `PromoVideo Capture` simulator; for Android it needs a running emulator or a
connected device, and says so when there is none. Screens beyond the first are reached only
through deep links the app itself declares (URL schemes + its routes); otherwise the report
says navigation was not possible. Every command goes through `run`, so tests can mock it.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from .config import Workspace

SIM_NAME = "PromoVideo Capture"
Run = Callable[..., subprocess.CompletedProcess]


def default_run(cmd: list[str], *, cwd: str | Path | None = None, timeout: float = 600,
                binary: bool = False) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=not binary, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, b"" if binary else "", f"{cmd[0]}: command not found")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, b"" if binary else "", f"{cmd[0]}: timed out after {timeout:.0f}s")


def detect_platforms(root: Path) -> list[dict]:
    found = []
    pub = root / "pubspec.yaml"
    if pub.is_file() and re.search(r"^\s*flutter\s*:", pub.read_text(errors="replace"), re.M):
        found.append({"platform": "flutter", "evidence": "pubspec.yaml",
                      "targets": [t for t in ("ios", "android", "web") if (root / t).is_dir()]})
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            deps = json.loads(pkg.read_text()).get("dependencies") or {}
        except json.JSONDecodeError:
            deps = {}
        if "react-native" in deps or "expo" in deps:
            found.append({"platform": "react-native", "evidence": "package.json"})
    if not any(f["platform"] in ("flutter", "react-native") for f in found):
        proj = sorted(root.glob("*.xcodeproj")) + sorted(root.glob("ios/*.xcodeproj"))
        if proj:
            found.append({"platform": "ios", "evidence": proj[0].relative_to(root).as_posix()})
        for g in ("app/build.gradle", "app/build.gradle.kts", "android/app/build.gradle", "android/app/build.gradle.kts"):
            f = root / g
            if f.is_file() and "com.android.application" in f.read_text(errors="replace"):
                found.append({"platform": "android", "evidence": g})
                break
    return found


def ios_devices(run: Run) -> tuple[list[dict], str | None]:
    res = run(["xcrun", "simctl", "list", "devices", "available", "-j"], timeout=60)
    if res.returncode != 0:
        return [], "no iOS Simulator (Xcode command-line tools not available)"
    try:
        data = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return [], "could not read the simulator list"
    out = []
    for runtime, devs in (data.get("devices") or {}).items():
        if "iOS" not in runtime:
            continue
        for d in devs:
            out.append({"id": d["udid"], "name": d["name"], "state": d.get("state"), "runtime": runtime,
                        "platform": "ios", "kind": "simulator"})
    return out, None if out else "no iOS simulators are installed"


def android_devices(run: Run) -> tuple[list[dict], str | None]:
    res = run(["adb", "devices"], timeout=30)
    if res.returncode != 0:
        return [], "adb is not available (Android SDK platform-tools not installed)"
    out = []
    for ln in (res.stdout or "").splitlines()[1:]:
        parts = ln.split()
        if len(parts) >= 2 and parts[1] == "device":
            out.append({"id": parts[0], "name": parts[0], "state": "online", "platform": "android",
                        "kind": "emulator" if parts[0].startswith("emulator-") else "device"})
    if out:
        return out, None
    avds = run(["emulator", "-list-avds"], timeout=30)
    if avds.returncode == 127:
        return [], "no Android emulator or device: the Android emulator is not installed and no device is connected"
    if not (avds.stdout or "").strip():
        return [], "no Android emulator or device: no AVDs exist and no device is connected"
    return [], ("an Android emulator exists but none is running and no device is connected; start one "
                f"(e.g. `emulator -avd {(avds.stdout or '').split()[0]}`) and re-run")


def own_simulator(run: Run, devices: list[dict]) -> tuple[dict | None, bool, str | None]:
    """promo's own simulator: reuse it, or create it from the newest iPhone runtime."""
    mine = next((d for d in devices if d["name"] == SIM_NAME), None)
    if mine:
        return mine, False, None
    runtimes = run(["xcrun", "simctl", "list", "runtimes", "available", "-j"], timeout=60)
    try:
        ios = [r for r in json.loads(runtimes.stdout)["runtimes"]
               if r.get("platform", "iOS") == "iOS" and r.get("isAvailable", True)]
        rt = ios[-1]
        # Only a device type the runtime supports can be created; prefer the newest plain iPhone.
        phones = [(t.get("name", ""), t["identifier"]) for t in rt.get("supportedDeviceTypes", [])
                  if re.fullmatch(r"iPhone \d+( Pro)?", t.get("name", ""))]
        if not phones:
            types = json.loads(run(["xcrun", "simctl", "list", "devicetypes", "-j"], timeout=60).stdout)["devicetypes"]
            phones = [(t["name"], t["identifier"]) for t in types if re.fullmatch(r"iPhone \d+( Pro)?", t["name"])]
        dtype = max(phones, key=lambda p: (int(re.search(r"\d+", p[0]).group(0)), "Pro" not in p[0]))[1]
        rt = rt["identifier"]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError, AttributeError):
        return None, False, "could not find an iPhone device type and iOS runtime to create a capture simulator"
    made = run(["xcrun", "simctl", "create", SIM_NAME, dtype, rt], timeout=120)
    if made.returncode != 0:
        return None, False, f"could not create a simulator: {(made.stderr or '').strip()[:200]}"
    return {"id": made.stdout.strip(), "name": SIM_NAME, "state": "Shutdown", "platform": "ios",
            "kind": "simulator"}, True, None


def deep_links(root: Path, platform: str) -> tuple[str | None, list[str]]:
    """The app's own URL scheme and the routes it declares (Flutter routes / go_router paths)."""
    scheme = None
    for plist in list(root.glob("ios/Runner/Info.plist")) + list(root.glob("*/Info.plist")):
        m = re.search(r"<key>CFBundleURLSchemes</key>\s*<array>\s*<string>([^<]+)</string>", plist.read_text(errors="replace"))
        if m:
            scheme = m.group(1)
            break
    if not scheme:
        for man in root.glob("**/AndroidManifest.xml"):
            m = re.search(r'android:scheme="([a-z][\w+.-]*)"', man.read_text(errors="replace"))
            if m and m.group(1) not in ("http", "https"):
                scheme = m.group(1)
                break
    routes: list[str] = []
    for dart in (root / "lib").rglob("*.dart") if (root / "lib").is_dir() else []:
        text = dart.read_text(errors="replace")
        routes += re.findall(r"['\"](/[\w/-]*)['\"]\s*:\s*\(", text)  # MaterialApp(routes: {'/x': (ctx) => …})
        routes += re.findall(r"GoRoute\(\s*path\s*:\s*['\"](/[\w/-]*)['\"]", text)
    return scheme, list(dict.fromkeys(r for r in routes if r != "/"))


def bundle_id(app: Path, run: Run) -> str | None:
    res = run(["plutil", "-extract", "CFBundleIdentifier", "raw", str(app / "Info.plist")], timeout=30)
    return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else None


def android_app_id(root: Path) -> str | None:
    for g in ("android/app/build.gradle", "android/app/build.gradle.kts", "app/build.gradle", "app/build.gradle.kts"):
        f = root / g
        if f.is_file():
            m = re.search(r"applicationId\s*=?\s*['\"]([\w.]+)['\"]", f.read_text(errors="replace"))
            if m:
                return m.group(1)
    return None


def _structure(path: Path):
    from .reference import _frame_at, _luma, _z
    raw = _frame_at(path, 0, 64, 36)
    return _z(_luma(raw)) if raw else None


def _differ(a, b) -> float:
    from .reference import _mad
    return _mad(a, b) if a and b else 1.0


def stable_capture(capture, dest: Path, *, wait: float, tries: int = 4) -> tuple[bool, str | None]:
    """Capture until two shots taken `wait` apart agree: system banners, toasts and entrance
    animations come and go, the screen itself stays. Returns (ok, problem)."""
    probe = dest.with_name(dest.stem + ".probe.png")
    try:
        for _ in range(tries):
            if not (capture(probe) and capture_after(capture, dest, wait)):
                return False, "the screenshot command failed"
            if _differ(_structure(probe), _structure(dest)) < 0.06:
                return (True, None) if _shot_ok(dest) else (False, "blank screen")
            time.sleep(wait)
        return False, "the screen kept changing (a notification or an animation that never settled)"
    finally:
        probe.unlink(missing_ok=True)


def capture_after(capture, dest: Path, wait: float) -> bool:
    time.sleep(wait)
    return capture(dest)


def _shot_ok(path: Path) -> bool:
    from .reference import _frame_at, _luma, detail
    raw = _frame_at(path, 0, 64, 36)
    return bool(raw) and detail(_luma(raw)) > 0.0012


def inspect_mobile(ws: Workspace, *, product_root: Path, platforms: list[dict], run: Run = default_run,
                   settle: float = 3.0, keep_simulator: bool = False) -> dict:
    report: dict = {"platform": None, "status": "not-started", "device": None, "launch": None, "screens": [],
                    "shots": [], "limitations": [], "stage": None, "devicesSeen": []}
    plat = next((p for p in platforms if p["platform"] in ("flutter", "ios", "android")), None)
    if not plat:
        if any(p["platform"] == "react-native" for p in platforms):
            report.update(platform="react-native", status="blocked", stage="platform")
            report["limitations"].append("React Native / Expo apps need a Metro server and a device session; "
                                         "launching them is not automated. Supply screenshots instead.")
        else:
            report.update(status="not-applicable")
        return report
    report["platform"] = plat["platform"]
    want_ios = plat["platform"] == "ios" or (plat["platform"] == "flutter" and "ios" in plat.get("targets", ["ios"]))
    want_android = plat["platform"] == "android" or (plat["platform"] == "flutter" and "android" in plat.get("targets", ["android"]))
    created = False
    device = None
    if want_ios:
        devs, why = ios_devices(run)
        report["devicesSeen"] += [f"{d['name']} ({d['state']})" for d in devs]
        if devs:
            device, created, why = own_simulator(run, devs)
        if not device:
            report["limitations"].append(f"iOS: {why or 'no iOS simulator available'}")
    if device is None and want_android:
        devs, why = android_devices(run)
        report["devicesSeen"] += [d["name"] for d in devs]
        if devs:
            device = devs[0]
        else:
            report["limitations"].append(f"Android: {why}")
    if device is None:
        report.update(status="blocked", stage="device discovery")
        return report
    report["device"] = {k: device[k] for k in ("id", "name", "platform", "kind")} | {"createdByPromo": created}
    try:
        return _launch_and_capture(ws, product_root, plat, device, run, report, settle)
    finally:
        if device["platform"] == "ios":
            run(["xcrun", "simctl", "shutdown", device["id"]], timeout=120)
            if created and not keep_simulator:
                run(["xcrun", "simctl", "delete", device["id"]], timeout=120)


def _launch_and_capture(ws, root, plat, device, run, report, settle) -> dict:
    out_dir = ws.captured / "mobile"
    out_dir.mkdir(parents=True, exist_ok=True)
    udid = device["id"]
    if device["platform"] == "ios":
        boot = run(["xcrun", "simctl", "boot", udid], timeout=300)
        if boot.returncode != 0 and "Booted" not in (boot.stderr or ""):
            report.update(status="blocked", stage="boot simulator")
            report["limitations"].append(f"simulator did not boot: {(boot.stderr or '').strip()[:200]}")
            return report
        run(["xcrun", "simctl", "bootstatus", udid, "-b"], timeout=600)
        run(["xcrun", "simctl", "status_bar", udid, "override", "--time", "9:41", "--batteryState", "charged",
             "--batteryLevel", "100", "--cellularBars", "4", "--wifiBars", "3"], timeout=60)
        if plat["platform"] == "flutter":
            build = run(["flutter", "build", "ios", "--simulator", "--debug"], cwd=root, timeout=2400)
            app = root / "build" / "ios" / "iphonesimulator" / "Runner.app"
            report["launch"] = {"build": "flutter build ios --simulator --debug",
                                "note": "Flutter writes its build output to the product's build/ folder (generated, not source)"}
        else:
            dd = ws.root / "build" / "mobile-derived-data"
            lst = run(["xcodebuild", "-list", "-json"], cwd=root, timeout=120)
            try:
                info = json.loads(lst.stdout or "{}")
                scheme = (info.get("project") or info.get("workspace") or {}).get("schemes", [None])[0]
            except json.JSONDecodeError:
                scheme = None
            if not scheme:
                report.update(status="blocked", stage="build")
                report["limitations"].append("could not read an Xcode scheme (`xcodebuild -list`)")
                return report
            build = run(["xcodebuild", "-scheme", scheme, "-sdk", "iphonesimulator", "-destination", f"id={udid}",
                         "-derivedDataPath", str(dd), "build"], cwd=root, timeout=2400)
            apps = sorted((dd / "Build" / "Products").glob("*-iphonesimulator/*.app"))
            app = apps[0] if apps else dd / "missing.app"
            report["launch"] = {"build": f"xcodebuild -scheme {scheme} (derived data in the workspace)"}
        if build.returncode != 0 or not app.exists():
            tail = " ".join(((build.stderr or "") + (build.stdout or "")).split())[-400:]
            report.update(status="blocked", stage="build")
            report["limitations"].append(f"the app did not build: {tail}")
            return report
        bid = bundle_id(app, run)
        inst = run(["xcrun", "simctl", "install", udid, str(app)], timeout=300)
        if bid and inst.returncode == 0:
            # Warm-up: a freshly booted simulator shows first-boot banners; let them pass.
            run(["xcrun", "simctl", "launch", udid, bid], timeout=120)
            time.sleep(settle * 3)
            run(["xcrun", "simctl", "terminate", udid, bid], timeout=60)
        launch = run(["xcrun", "simctl", "launch", udid, bid or ""], timeout=120) if bid else None
        if inst.returncode != 0 or not launch or launch.returncode != 0:
            report.update(status="blocked", stage="install/launch")
            report["limitations"].append("the app built but did not install or launch: "
                                         + ((launch.stderr if launch else "no bundle id") or "")[:200])
            return report
        report["launch"]["bundleId"] = bid

        def capture(dest: Path) -> bool:
            return run(["xcrun", "simctl", "io", udid, "screenshot", str(dest)], timeout=60).returncode == 0

        open_route = None  # iOS custom-scheme links need a person to confirm; never used unattended
    else:
        gradle_dir = root / "android" if (root / "android" / "gradlew").exists() else root
        build = run(["./gradlew", "installDebug"], cwd=gradle_dir, timeout=2400)
        app_id = android_app_id(root)
        if build.returncode != 0 or not app_id:
            report.update(status="blocked", stage="build")
            report["limitations"].append("the app did not build/install: "
                                         + " ".join((build.stderr or build.stdout or "").split())[-300:])
            return report
        launch = run(["adb", "-s", udid, "shell", "monkey", "-p", app_id, "-c", "android.intent.category.LAUNCHER", "1"],
                     timeout=120)
        if launch.returncode != 0:
            report.update(status="blocked", stage="launch")
            report["limitations"].append(f"the app installed but did not launch: {(launch.stderr or '')[:200]}")
            return report
        report["launch"] = {"build": "./gradlew installDebug", "applicationId": app_id}

        def capture(dest: Path) -> bool:
            res = run(["adb", "-s", udid, "exec-out", "screencap", "-p"], timeout=60, binary=True)
            if res.returncode == 0 and res.stdout:
                dest.write_bytes(res.stdout)
                return True
            return False

        def open_route(url: str) -> bool:
            return run(["adb", "-s", udid, "shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url,
                        app_id], timeout=60).returncode == 0

    time.sleep(settle)
    first = out_dir / f"{device['platform']}-launch.png"
    ok, problem = stable_capture(capture, first, wait=max(settle / 2, 0.01))
    taken: list[tuple[str, object]] = []
    if ok:
        report["shots"].append({"path": first, "screen": "launch", "route": "/"})
        report["screens"].append({"screen": "launch", "route": "/", "finding": "renders"})
        taken.append(("launch", _structure(first)))
    else:
        report["screens"].append({"screen": "launch", "route": "/", "finding": problem})
    scheme, routes = deep_links(root, device["platform"])
    # How to reach a route without a person tapping: Flutter reads an initial route from its
    # launch arguments; Android opens deep links directly. iOS custom-scheme links raise a
    # system "Open in …?" confirmation, so they cannot be followed unattended.
    if plat["platform"] == "flutter" and device["platform"] == "ios":
        how = "launch argument --route"
    elif device["platform"] == "android" and scheme:
        how = "deep link"
    else:
        how = None
        if routes:
            report["limitations"].append(
                f"the app declares {len(routes)} route(s), but they cannot be reached unattended here "
                + ("(iOS asks the user to confirm custom-scheme links)" if device["platform"] == "ios" and scheme
                   else "(no URL scheme is declared)") + "; only the launch screen was captured. Supply the others "
                "with `promo discover --supplied`, or add a UI test that navigates.")
    for r in routes[:6] if how else []:
        name = re.sub(r"[^a-z0-9]+", "-", r.lower()).strip("-")
        dest = out_dir / f"{device['platform']}-{name}.png"
        if how == "launch argument --route":
            run(["xcrun", "simctl", "terminate", udid, report["launch"]["bundleId"]], timeout=60)
            nav = run(["xcrun", "simctl", "launch", udid, report["launch"]["bundleId"], f"--route={r}"], timeout=120)
            moved = nav.returncode == 0
        else:
            moved = open_route(f"{scheme}://app{r}")
        if not moved:
            report["screens"].append({"screen": r, "route": r, "finding": "navigation failed"})
            continue
        time.sleep(settle)
        ok, problem = stable_capture(capture, dest, wait=max(settle / 2, 0.01))
        if not ok:
            report["screens"].append({"screen": r, "route": r, "finding": problem})
            continue
        # A capture that matches one already taken did not reach a new screen; it is never
        # reported as one.
        st = _structure(dest)
        same = next((n for n, other in taken if _differ(st, other) < 0.10), None)
        if same:
            dest.unlink(missing_ok=True)
            report["screens"].append({"screen": r, "route": r, "finding": f"did not navigate (same screen as {same})"})
            continue
        taken.append((r, st))
        report["shots"].append({"path": dest, "screen": r.strip("/"), "route": r})
        report["screens"].append({"screen": r, "route": r, "finding": f"renders (reached by {how})"})
    if not scheme and not routes:
        report["limitations"].append("no routes declared: only the launch screen was captured automatically")
    report["status"] = "captured" if report["shots"] else "blocked"
    if not report["shots"]:
        report["stage"] = "capture"
    return report
