"""Product capture: screenshots of the real, running product.

Uses a headless Chrome already on the machine (system Chrome/Chromium, or the one Remotion
downloads), so capture adds no dependency. With `launch`, the product's own dev command
(from product-scan.json) is started, polled until it answers, captured, and stopped.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urljoin

from .config import Workspace
from .util import RENDERER_DIR, PromoError, scrub

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
    proc, fh = None, None
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
            dest = ws.captured / "web" / f"{slug}-{size}.png"
            out.append(screenshot(chrome, urljoin(url.rstrip("/") + "/", r.lstrip("/")), dest, SIZES[size]))
        return out
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if fh:
            fh.close()
        _scrub_log(log)


# ── live inspection of a web product (PRODUCT_THEME_DISCOVERY) ─────────────────────

# Scripts that could touch real data or infrastructure are never run to take a screenshot.
UNSAFE_SCRIPT = re.compile(r"\b(migrat\w*|seed|reset|drop|truncate|deploy|publish|release|--prod\b|vercel|netlify|"
                           r"wrangler\s+(?:deploy|publish)|firebase\s+deploy|rm\s+-rf|db:push|prisma\s+db\s+push)\b", re.I)
SAFE_SCRIPTS = ("dev", "start", "preview", "serve")
ERROR_SIGNS = re.compile(r"Unhandled Runtime Error|Application error: a client-side exception|Internal Server Error|"
                         r"Hydration failed|There was an error while hydrating|\[plugin:vite|Failed to compile|"
                         r"Module not found|Cannot GET /|ReferenceError|TypeError: ", re.I)
AUTH_PATH = re.compile(r"/(login|signin|sign-in|auth|sso|account/login)\b", re.I)


def http_probe(url: str, timeout: float = 8) -> dict:
    """Status code and final URL after redirects; never raises for HTTP errors."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            body = res.read(400_000).decode(errors="replace")
            return {"status": res.status, "final": res.geturl(), "body": body}
    except urllib.error.HTTPError as exc:
        with exc:
            return {"status": exc.code, "final": exc.geturl() or url, "body": ""}
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
        return {"status": None, "final": url, "body": "", "error": str(exc)[:200]}


def dump_dom(chrome: str, url: str, budget_ms: int = 5000) -> str:
    res = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
                          f"--virtual-time-budget={budget_ms}", "--dump-dom", url],
                         capture_output=True, text=True, timeout=120)
    return res.stdout or ""


def read_dom(html: str) -> dict:
    """What a person would see: title, visible text, calls to action, referenced assets, errors."""
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    body = re.sub(r"<(script|style|noscript|template)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = " ".join(re.sub(r"<[^>]+>", " ", body).split())
    ctas = [" ".join(re.sub(r"<[^>]+>", " ", m).split())
            for m in re.findall(r"<(?:button|a)\b[^>]*>(.*?)</(?:button|a)>", html, re.S | re.I)]
    assets = re.findall(r"<(?:img|script|link)\b[^>]*(?:src|href)=['\"]([^'\"]+)['\"]", html, re.I)
    errors = sorted({m.group(0) for m in ERROR_SIGNS.finditer(text)})
    head = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.S | re.I) or re.search(r"<h2\b[^>]*>(.*?)</h2>", html, re.S | re.I)
    return {"title": html_unescape(title.group(1).strip()) if title else None, "textLength": len(text),
            "heading": html_unescape(" ".join(re.sub(r"<[^>]+>", " ", head.group(1)).split())) if head else None,
            "text": text[:600], "ctas": [c for c in ctas if 1 < len(c) < 40][:12],
            "assets": [a for a in assets if not a.startswith(("data:", "http://", "https://", "//", "#"))][:40],
            "errors": errors, "images": len(re.findall(r"<img\b", html, re.I))}


def html_unescape(s: str) -> str:
    import html
    return html.unescape(s)


def check_launch_command(plan: dict) -> None:
    script = plan.get("script") or plan.get("command") or ""
    name = (plan.get("command") or "").split()[-1] if plan.get("command") else ""
    if plan.get("command", "").startswith("npm run") and name not in SAFE_SCRIPTS:
        raise PromoError(f"refusing to run `{plan['command']}` for screenshots: only {', '.join(SAFE_SCRIPTS)} scripts are run")
    if UNSAFE_SCRIPT.search(script):
        raise PromoError(f"refusing to run `{plan.get('command')}` (`{script}`): it looks like it changes data or "
                         "infrastructure", hint="start the product yourself against test data and pass --url")


def is_this_product(url: str, names: list[str]) -> bool:
    """A server already on the port is reused only if what it serves names this product."""
    probe = http_probe(url)
    if probe.get("status") is None:
        return False
    hay = (probe.get("body") or "").lower()
    return any(n and n.lower() in hay for n in names)


def inspect_web(ws: Workspace, *, product_root: Path, plan: dict, url: str | None, routes: list[str],
                names: list[str], size: str = "desktop", launch: bool = True, chrome: str | None = None,
                startup_timeout: float = 90) -> dict:
    """Launch (or reuse) the product, check each route, capture the ones that render.

    Returns a report: launch outcome, per-route findings, screenshot paths, limitations. Never
    raises for an individual route; raises only when nothing could be inspected at all."""
    report: dict = {"platform": "web", "status": "not-started", "url": url or plan.get("url"), "launch": None,
                    "routes": [], "limitations": [], "shots": []}
    url = report["url"]
    if not url:
        report.update(status="blocked", stage="launch plan")
        report["limitations"].append("no local URL is known for the product (no dev script with a port)")
        return report
    try:
        chrome = chrome or find_chrome()
    except PromoError as exc:
        report.update(status="blocked", stage="browser")
        report["limitations"].append(str(exc))
        return report
    proc, log, fh = None, ws.root / "build" / "launch.log", None
    try:
        up = http_probe(url).get("status") is not None
        if up:
            if not is_this_product(url, names):
                report.update(status="blocked", stage="launch")
                report["limitations"].append(f"{url} is already serving something that does not name "
                                             f"{names[0] if names else 'the product'}; it was not used or stopped")
                return report
            report["launch"] = {"how": "reused a server already running this product", "url": url}
        elif launch:
            check_launch_command(plan)
            cwd = product_root / (plan.get("cwd") or ".")
            log.parent.mkdir(parents=True, exist_ok=True)
            fh = open(log, "w")
            proc = subprocess.Popen(plan["command"], shell=True, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                wait_for(url, startup_timeout)
            except PromoError:
                tail = scrub(log.read_text(errors="replace"))[-800:] if log.exists() else ""
                report.update(status="blocked", stage="dev server startup")
                report["limitations"].append(f"`{plan['command']}` did not serve {url}: " + " ".join(tail.split())[-300:])
                return report
            if proc.poll() is not None:
                report.update(status="blocked", stage="dev server startup")
                report["limitations"].append(f"`{plan['command']}` exited (code {proc.returncode})")
                return report
            report["launch"] = {"how": f"started `{plan['command']}` in {plan.get('cwd') or '.'}", "url": url,
                                "log": "build/launch.log"}
        else:
            report.update(status="blocked", stage="launch")
            report["limitations"].append(f"nothing is serving {url} and launching was not requested")
            return report
        base = url.rstrip("/") + "/"
        for r in routes or ["/"]:
            full = urljoin(base, r.lstrip("/"))
            probe = http_probe(full)
            row = {"route": r, "status": probe.get("status"), "final": probe.get("final")}
            final_path = urllib.parse.urlparse(probe.get("final") or full).path
            if probe.get("status") is None or probe["status"] >= 400:
                row["finding"] = f"unavailable (HTTP {probe.get('status') or 'no response'})"
                report["routes"].append(row)
                continue
            if AUTH_PATH.search(final_path) and not AUTH_PATH.search(r):
                row["finding"] = f"requires authentication (redirected to {final_path})"
                report["routes"].append(row)
                report["limitations"].append(f"{r}: behind a login; not captured (no test account was provided)")
                continue
            dom = read_dom(dump_dom(chrome, full))
            row.update(title=dom["title"], heading=dom["heading"], textLength=dom["textLength"], ctas=dom["ctas"],
                       errors=dom["errors"])
            broken = []
            for a in dom["assets"][:20]:
                st = http_probe(urljoin(full, a)).get("status")
                if st is None or st >= 400:
                    broken.append(a)
            row["brokenAssets"] = broken
            if dom["textLength"] < 20 and dom["images"] == 0:
                row["finding"] = "blank page"
            elif dom["errors"]:
                row["finding"] = "runtime error on screen: " + ", ".join(dom["errors"][:2])
            elif broken:
                row["finding"] = f"{len(broken)} broken asset(s)"
            else:
                row["finding"] = "renders"
            dest = ws.captured / "web" / f"{slug_route(r)}-{size}.png"
            try:
                screenshot(chrome, full, dest, SIZES[size])
                row["shot"] = dest
                report["shots"].append({"path": dest, "route": r, "title": dom["title"], "heading": dom["heading"],
                                        "finding": row["finding"]})
            except PromoError as exc:
                row["finding"] += f"; capture failed: {exc}"
            report["routes"].append(row)
        ok = [x for x in report["routes"] if x.get("finding") == "renders"]
        report["status"] = "captured" if ok else "blocked"
        if not ok:
            report["stage"] = "routes"
            report["limitations"].append("no route rendered cleanly")
        return report
    finally:
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if fh:
            fh.close()
        _scrub_log(log)


def _scrub_log(log: Path) -> None:
    """The server's own output can print connection strings; keep the diagnostic, drop the secret."""
    if log.exists():
        log.write_text(scrub(log.read_text(errors="replace")))


def slug_route(route: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", route.lower()).strip("-")
    return s or "home"
