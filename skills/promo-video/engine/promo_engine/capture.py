"""Product capture: screenshots of the real, running product.

Uses a headless Chrome already on the machine (system Chrome/Chromium, or the one Remotion
downloads), so capture adds no dependency. With `launch`, the product's own dev command
(from product-scan.json) is started, polled until it answers, captured, and stopped.
"""
from __future__ import annotations

import glob
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from .config import Workspace
from .util import RENDERER_DIR, PromoError

SIZES = {"desktop": (1920, 1080), "laptop": (1440, 900), "phone": (430, 932)}


def find_chrome() -> str:
    env = os.environ.get("PROMO_CHROME")
    cands = [env] if env else []
    cands += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              shutil.which("google-chrome") or "", shutil.which("chromium") or "",
              shutil.which("chromium-browser") or "", shutil.which("chrome") or ""]
    cands += sorted(glob.glob(str(RENDERER_DIR / "node_modules/.remotion/chrome-headless-shell/*/*/chrome-headless-shell")))
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    raise PromoError("no Chrome/Chromium found for capturing the product",
                     hint="install Chrome, set PROMO_CHROME, or run `npx remotion browser ensure` in the renderer")


def wait_for(url: str, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as res:
                if res.status < 500:
                    return
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(1.0)
    raise PromoError(f"the product did not respond at {url} within {timeout:.0f}s ({last})")


def screenshot(chrome: str, url: str, dest: Path, size: tuple[int, int], budget_ms: int = 6000) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
           "--force-device-scale-factor=2" if w < 800 else "--force-device-scale-factor=1",
           f"--window-size={w},{h}", f"--virtual-time-budget={budget_ms}", f"--screenshot={dest}", url]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 or not dest.is_file():
        raise PromoError(f"could not capture {url}: {res.stderr.strip()[-300:]}")
    return dest


def capture(ws: Workspace, *, url: str | None, routes: list[str], size: str = "desktop",
            launch: bool = False, launch_cmd: str | None = None, cwd: Path | None = None) -> list[Path]:
    chrome = find_chrome()
    proc = None
    log = ws.root / "build" / "launch.log"
    try:
        if launch:
            if not launch_cmd or not url:
                raise PromoError("don't know how to launch this product",
                                 hint="pass --cmd and --url, or start it yourself and pass --url")
            log.parent.mkdir(parents=True, exist_ok=True)
            fh = open(log, "w")
            proc = subprocess.Popen(launch_cmd, shell=True, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                wait_for(url)
            except PromoError as exc:
                tail = log.read_text()[-600:] if log.exists() else ""
                raise PromoError(f"the product failed to launch with `{launch_cmd}`: {exc}\n{tail}",
                                 hint="fix the launch (env vars, install step) or capture screens manually "
                                      "into promo/assets/; never substitute invented UI") from exc
        if not url:
            raise PromoError("no URL to capture")
        out = []
        for r in routes or ["/"]:
            slug = (r.strip("/").replace("/", "-") or "home")
            dest = ws.assets / "captures" / f"{slug}-{size}.png"
            out.append(screenshot(chrome, urljoin(url.rstrip("/") + "/", r.lstrip("/")), dest, SIZES[size]))
        return out
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
