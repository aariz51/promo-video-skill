"""Layer 2: PRODUCT ANALYZER.

Walks the product repository and records what is *evidenced* there: manifests, README,
docs, routes and screens, commands, assets, brand tokens, tests and how to launch it.
Every finding carries the path it came from. The output, `product-scan.json`, is a map
for the agent, which then reads the files it points to and writes the PRODUCT PROMO BRIEF.

Security: `.env` files and anything whose name suggests a secret are never read; only the
variable *names* in `.env.example`-style templates are recorded.
"""
from __future__ import annotations

import json
import os
import re
import struct
import tomllib
from collections import Counter
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".nuxt", "out", "coverage", "Pods",
    ".dart_tool", ".venv", "venv", "env", "__pycache__", ".gradle", "target", ".turbo",
    ".cache", ".idea", ".vscode", "DerivedData", ".expo", ".svelte-kit", "vendor", "promo",
    ".pytest_cache", ".mypy_cache", ".output", "storybook-static",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".avif"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
TEXT_EXT = {".md", ".mdx", ".txt", ".json", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py",
            ".dart", ".swift", ".kt", ".go", ".rs", ".rb", ".css", ".scss", ".html", ".vue",
            ".svelte", ".yaml", ".yml", ".toml"}
SECRET_NAME = re.compile(r"(secret|api[\s_-]*key|private[\s_-]*key|token|credential|password|\.pem$|\.p8$|\.key$)", re.I)
ENV_TEMPLATE = re.compile(r"^\.env\.(example|sample|template|dist)$")
MAX_FILES = 25000
MAX_TEXT_BYTES = 1_500_000

FRAMEWORKS = {
    "next": "Next.js", "react": "React", "vue": "Vue", "svelte": "Svelte", "@sveltejs/kit": "SvelteKit",
    "vite": "Vite", "expo": "Expo", "react-native": "React Native", "electron": "Electron",
    "remotion": "Remotion", "express": "Express", "fastify": "Fastify", "hono": "Hono",
    "@nestjs/core": "NestJS", "astro": "Astro", "nuxt": "Nuxt", "@angular/core": "Angular",
    "tailwindcss": "Tailwind CSS", "three": "three.js", "prisma": "Prisma", "@prisma/client": "Prisma",
    "openai": "OpenAI SDK", "@anthropic-ai/sdk": "Anthropic SDK", "fastapi": "FastAPI", "flask": "Flask",
    "django": "Django", "streamlit": "Streamlit", "typer": "Typer", "click": "Click",
}
DEV_PORTS = {"Next.js": 3000, "Vite": 5173, "Astro": 4321, "Nuxt": 3000, "SvelteKit": 5173,
             "Angular": 4200, "Remotion": 3000, "Streamlit": 8501, "FastAPI": 8000, "Flask": 5000,
             "Django": 8000, "Express": 3000}

_COLOR = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|(?:rgb|hsl|oklch)a?\([^)]{3,60}\)")
_CSS_VAR = re.compile(r"(--[\w-]+)\s*:\s*([^;}{]+)")
_FLUTTER_COLOR = re.compile(r"Color\(0x([0-9A-Fa-f]{8})\)")
_FONT_FAMILY = re.compile(r"font-family\s*:\s*([^;}{]+)", re.I)
_NEXT_FONT = re.compile(r"import\s*\{([^}]+)\}\s*from\s*[\"']next/font/google[\"']")
_ROUTE_ATTR = re.compile(r"""\bpath\s*[:=]\s*[{]?\s*["'`](/[^"'`]*)["'`]""")
_HEADING = re.compile(r"^(#{1,3})\s+(.+?)\s*#*\s*$")


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _is_secret(name: str) -> bool:
    if name == ".env" or (name.startswith(".env") and not ENV_TEMPLATE.match(name)):
        return True
    return bool(SECRET_NAME.search(name)) and not ENV_TEMPLATE.match(name)


def _read(p: Path) -> str:
    try:
        if p.stat().st_size > MAX_TEXT_BYTES:
            return ""
        return p.read_text(errors="replace")
    except OSError:
        return ""


def image_size(p: Path) -> tuple[int, int] | None:
    """Width/height for PNG, JPEG, GIF and WebP from their headers (stdlib only)."""
    try:
        with open(p, "rb") as f:
            head = f.read(64 * 1024)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
        return struct.unpack(">II", head[16:24])
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", head[6:10])
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        chunk = head[12:16]
        if chunk == b"VP8X":
            w = int.from_bytes(head[24:27], "little") + 1
            h = int.from_bytes(head[27:30], "little") + 1
            return w, h
        if chunk == b"VP8 " and len(head) >= 30:
            w, h = struct.unpack("<HH", head[26:30])
            return w & 0x3FFF, h & 0x3FFF
        return None
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                i += 1
                continue
            marker = head[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return w, h
            seg = struct.unpack(">H", head[i + 2:i + 4])[0]
            i += 2 + seg
    return None


def walk(root: Path, exclude: Path | None = None):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        if exclude is not None and Path(dirpath).resolve() == exclude:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS and (not d.startswith(".") or d in (".github", ".claude")))
        for name in sorted(filenames):
            count += 1
            if count > MAX_FILES:
                return
            yield Path(dirpath) / name


def _readme_summary(text: str) -> dict:
    lines = text.splitlines()
    title, headings, para, in_code = None, [], [], False
    code_cmds: list[str] = []
    for ln in lines:
        if ln.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            s = ln.strip().lstrip("$ ").strip()
            if s and not s.startswith("#") and len(s) < 140:
                code_cmds.append(s)
            continue
        m = _HEADING.match(ln)
        if m:
            if title is None and m.group(1) == "#":
                title = m.group(2)
            headings.append(m.group(2))
            continue
        s = ln.strip()
        if title is not None and not para and s and not s.startswith(("[!", "<", "![", "|", ">")):
            para.append(s)
        elif para and s and len(" ".join(para)) < 500 and not s.startswith(("#", "|", "```", "-")):
            para.append(s)
        elif para and not s:
            break
    return {"title": title, "intro": " ".join(para)[:600], "headings": headings[:60],
            "codeCommands": code_cmds[:40]}


def _frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out, key = {}, None
    for ln in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", ln)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip().strip('"').lstrip(">-").strip()
        elif key and ln.startswith("  "):
            out[key] = (out[key] + " " + ln.strip()).strip()
    return out


def _next_route(rel: str) -> str | None:
    m = re.match(r"^(?:src/)?app/(.*)page\.(?:t|j)sx?$", rel)
    if m:
        segs = [s for s in m.group(1).split("/") if s and not (s.startswith("(") and s.endswith(")"))]
        return "/" + "/".join(segs)
    m = re.match(r"^(?:src/)?pages/(.*)\.(?:t|j)sx?$", rel)
    if m and not m.group(1).startswith(("_", "api/")):
        r = "/" + m.group(1)
        return re.sub(r"/index$", "", r) or "/"
    return None


def scan(root: str | Path, exclude: str | Path | None = None) -> dict:
    """`exclude` is the promo workspace, which must never be read as product."""
    root = Path(root).resolve()
    exclude = Path(exclude).resolve() if exclude else None
    manifests: dict = {}
    frameworks: set[str] = set()
    scripts: dict = {}
    readme: dict | None = None
    docs, routes, screens, images, videos, fonts, tests, skills, env_names = [], [], [], [], [], [], [], [], []
    colors: Counter = Counter()
    color_src: dict[str, str] = {}
    css_vars: list[dict] = []
    font_families: Counter = Counter()
    video_code: list[str] = []
    skipped_secrets: list[str] = []
    lang: Counter = Counter()
    file_count = 0

    for p in walk(root, exclude):
        file_count += 1
        rel = _rel(root, p)
        name = p.name
        ext = p.suffix.lower()
        if _is_secret(name):
            skipped_secrets.append(rel)
            continue
        if ext in TEXT_EXT:
            lang[ext] += 1
        if ENV_TEMPLATE.match(name):
            for ln in _read(p).splitlines():
                m = re.match(r"^\s*([A-Z][A-Z0-9_]+)\s*=", ln)
                if m:
                    env_names.append({"name": m.group(1), "source": rel})
            continue
        if ext in IMAGE_EXT:
            size = image_size(p) if ext != ".svg" else None
            role = "logo" if re.search(r"(logo|brand|wordmark|favicon|app[-_]?icon|icon[-_]?(512|1024))", rel, re.I) else (
                "screenshot" if re.search(r"(screen|shot|capture|preview|hero|demo)", rel, re.I) else "image")
            images.append({"path": rel, "size": list(size) if size else None, "bytes": p.stat().st_size, "role": role})
            continue
        if ext in VIDEO_EXT:
            videos.append({"path": rel, "bytes": p.stat().st_size})
            continue
        if ext in FONT_EXT:
            fonts.append(rel)
            continue
        if name == "package.json" and rel.count("/") <= 3:
            try:
                pkg = json.loads(_read(p) or "{}")
            except json.JSONDecodeError:
                pkg = {}
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            manifests[rel] = {"type": "npm", "name": pkg.get("name"), "description": pkg.get("description"),
                              "version": pkg.get("version"), "bin": pkg.get("bin"),
                              "dependencies": sorted(deps)[:80]}
            for d in deps:
                if d in FRAMEWORKS:
                    frameworks.add(FRAMEWORKS[d])
            for k, v in (pkg.get("scripts") or {}).items():
                scripts[f"{rel}:{k}"] = v
            if "remotion" in deps:
                video_code.append(rel)
            continue
        if name == "pyproject.toml":
            try:
                data = tomllib.loads(_read(p))
            except tomllib.TOMLDecodeError:
                data = {}
            proj = data.get("project", {})
            deps = proj.get("dependencies", [])
            manifests[rel] = {"type": "python", "name": proj.get("name"), "description": proj.get("description"),
                              "scripts": proj.get("scripts"), "dependencies": deps[:80]}
            for d in deps:
                key = re.split(r"[<>=\[ ;]", d)[0].lower()
                if key in FRAMEWORKS:
                    frameworks.add(FRAMEWORKS[key])
            continue
        if name == "pubspec.yaml":
            text = _read(p)
            nm = re.search(r"^name:\s*(\S+)", text, re.M)
            ds = re.search(r"^description:\s*(.+)$", text, re.M)
            manifests[rel] = {"type": "flutter", "name": nm.group(1) if nm else None,
                              "description": ds.group(1).strip().strip("\"'") if ds else None}
            frameworks.add("Flutter")
            continue
        if name in ("Cargo.toml", "go.mod", "Package.swift", "Gemfile", "composer.json"):
            manifests[rel] = {"type": name}
            continue
        if name == "SKILL.md":
            fm = _frontmatter(_read(p))
            skills.append({"path": rel, "name": fm.get("name"), "description": (fm.get("description") or "")[:400],
                           "userInvocable": fm.get("user-invocable") == "true"})
            continue
        if re.match(r"^readme(\.[a-z]+)?$", name, re.I) and readme is None and rel.count("/") == 0:
            readme = {"path": rel, **_readme_summary(_read(p))}
            continue
        if ext in (".md", ".mdx") and (rel.startswith("docs/") or rel.count("/") == 0):
            docs.append(rel)
        if re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(test|spec)\.[jt]sx?$|_test\.(py|go|dart)$|^test_.*\.py$", rel):
            tests.append(rel)
            continue
        route = _next_route(rel)
        if route is not None:
            routes.append({"route": route, "source": rel})
        if re.search(r"(Screen|Page|View)\.(t|j)sx$|_screen\.dart$|_page\.dart$|View\.swift$", name):
            screens.append(rel)
        if ext in (".css", ".scss", ".ts", ".tsx", ".js", ".jsx", ".dart", ".vue", ".svelte", ".html"):
            text = _read(p)
            if not text:
                continue
            if ext in (".tsx", ".jsx", ".ts", ".js") and ("<Route" in text or "createBrowserRouter" in text):
                for m in _ROUTE_ATTR.finditer(text):
                    routes.append({"route": m.group(1), "source": rel})
            if "from \"remotion\"" in text or "from 'remotion'" in text:
                video_code.append(rel)
            is_style = ext in (".css", ".scss") or re.search(r"(theme|tokens?|colors?|tailwind\.config|palette)", name, re.I)
            if is_style:
                for m in _CSS_VAR.finditer(text):
                    val = m.group(2).strip()
                    if _COLOR.search(val) and len(css_vars) < 120:
                        css_vars.append({"name": m.group(1), "value": val[:60], "source": rel})
                for c in _COLOR.findall(text):
                    key = c.lower()
                    colors[key] += 1
                    color_src.setdefault(key, rel)
                for f in _FONT_FAMILY.findall(text):
                    font_families[f.strip().split(",")[0].strip("'\" ")] += 1
            for m in _FLUTTER_COLOR.findall(text):
                key = "#" + m[2:].lower()
                colors[key] += 1
                color_src.setdefault(key, rel)
            for m in _NEXT_FONT.findall(text):
                for f in m.split(","):
                    font_families[f.strip().replace("_", " ")] += 1

    launch = _launch_plan(scripts, frameworks, manifests)
    project_type = _project_type(frameworks, manifests, skills)
    top_colors = [{"value": c, "count": n, "source": color_src[c]} for c, n in colors.most_common(12)]
    return {
        # Relative to the workspace when there is one: artifacts get committed and shared,
        # and an absolute path would leak the local user's home directory.
        "root": os.path.relpath(root, exclude) if exclude else ".",
        "fileCount": file_count,
        "projectType": project_type,
        "frameworks": sorted(frameworks),
        "languages": dict(lang.most_common(8)),
        "manifests": manifests,
        "readme": readme,
        "docs": sorted(docs)[:60],
        "skills": skills,
        "routes": _dedupe(routes, "route")[:80],
        "screens": screens[:80],
        "launch": launch,
        "assets": {
            "logos": [i for i in images if i["role"] == "logo"][:20],
            "screenshots": [i for i in images if i["role"] == "screenshot"][:40],
            "images": [i for i in images if i["role"] == "image"][:60],
            "videos": videos[:20],
            "fonts": fonts[:20],
        },
        "brand": {"colors": top_colors, "cssVariables": css_vars[:60],
                  "fontFamilies": [f for f, _ in font_families.most_common(6)]},
        "tests": {"count": len(tests), "sample": tests[:25]},
        "envVariables": _dedupe(env_names, "name"),
        "existingVideoCode": sorted(set(video_code))[:20],
        "skippedForSecurity": skipped_secrets,
    }


def _dedupe(items: list[dict], key: str) -> list[dict]:
    seen, out = set(), []
    for it in items:
        if it[key] not in seen:
            seen.add(it[key])
            out.append(it)
    return out


def _project_type(frameworks: set[str], manifests: dict, skills: list) -> str:
    if any(sk.get("userInvocable") for sk in skills):
        return "agent-skill"
    if "Flutter" in frameworks or "React Native" in frameworks or "Expo" in frameworks:
        return "mobile-app"
    if "Electron" in frameworks:
        return "desktop-app"
    if frameworks & {"Next.js", "Vite", "Astro", "Nuxt", "SvelteKit", "Angular", "React", "Vue", "Svelte"}:
        return "web-app"
    if frameworks & {"Express", "Fastify", "Hono", "NestJS", "FastAPI", "Flask", "Django"}:
        return "api-service"
    if skills:
        return "agent-skill"
    if any(m.get("bin") or m.get("scripts") for m in manifests.values()):
        return "cli-tool"
    if manifests:
        return "library"
    return "unknown"


def _launch_plan(scripts: dict, frameworks: set[str], manifests: dict) -> dict:
    """How to run the product locally, as far as the repository says."""
    for want in ("dev", "start", "preview", "serve"):
        for key, cmd in scripts.items():
            pkg, name = key.rsplit(":", 1)
            if name == want:
                port = next((DEV_PORTS[f] for f in ("Next.js", "Vite", "Astro", "Nuxt", "SvelteKit", "Angular", "Remotion", "Express")
                             if f in frameworks), None)
                pm = re.search(r"--port[= ](\d+)|-p (\d+)", cmd)
                if pm:
                    port = int(pm.group(1) or pm.group(2))
                cwd = str(Path(pkg).parent) if "/" in pkg else "."
                return {"command": f"npm run {name}", "cwd": cwd, "script": cmd,
                        "url": f"http://localhost:{port}" if port else None, "source": pkg}
    if "Flutter" in frameworks:
        return {"command": "flutter run -d chrome", "cwd": ".", "url": None, "source": "pubspec.yaml"}
    for f, port in (("Streamlit", 8501), ("FastAPI", 8000), ("Flask", 5000), ("Django", 8000)):
        if f in frameworks:
            return {"command": None, "cwd": ".", "url": f"http://localhost:{port}", "source": "pyproject.toml"}
    return {"command": None, "cwd": ".", "url": None, "source": None}


def summarize(scan_data: dict, root: Path | None = None) -> str:
    r = scan_data.get("readme") or {}
    a = scan_data["assets"]
    lines = [
        f"Product root: {root or scan_data['root']}  ({scan_data['fileCount']} files)",
        f"Type: {scan_data['projectType']} · frameworks: {', '.join(scan_data['frameworks']) or 'none detected'}",
        f"README: {r.get('title') or '—'} — {(r.get('intro') or '')[:140]}",
        f"Routes: {len(scan_data['routes'])} · screens: {len(scan_data['screens'])} · skills: {len(scan_data['skills'])} · tests: {scan_data['tests']['count']}",
        f"Assets: {len(a['logos'])} logos · {len(a['screenshots'])} screenshots · {len(a['images'])} other images · {len(a['videos'])} videos",
        f"Brand colours: {', '.join(c['value'] for c in scan_data['brand']['colors'][:6]) or '—'}",
        f"Launch: {scan_data['launch'].get('command') or 'not determined'} {scan_data['launch'].get('url') or ''}".rstrip(),
    ]
    if scan_data["skippedForSecurity"]:
        lines.append(f"Not read (secret-like names): {len(scan_data['skippedForSecurity'])} file(s)")
    return "\n".join(lines)


def _rgb(hexv: str) -> tuple[float, float, float] | None:
    h = hexv.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return None
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def brand_accent(scan_data: dict) -> dict | None:
    """The product's accent colour, from evidence: a design token named brand / primary /
    accent first, otherwise the most saturated mid-tone colour the code uses."""
    brand = (scan_data or {}).get("brand") or {}
    for var in brand.get("cssVariables", []):
        if re.search(r"brand|primary|accent", var["name"], re.I) and _rgb(var["value"]):
            return {"value": "#" + var["value"].lstrip("#").upper()[:6], "source": var["source"],
                    "why": f"design token {var['name']}"}
    best = None
    for c in brand.get("colors", []):
        rgb = _rgb(c["value"])
        if not rgb:
            continue
        hi, lo = max(rgb), min(rgb)
        sat = (hi - lo) / hi if hi else 0
        lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        if sat > 0.3 and 0.12 < lum < 0.85 and (best is None or sat > best[0]):
            best = (sat, c)
    if best:
        c = best[1]
        return {"value": "#" + c["value"].lstrip("#").upper()[:6], "source": c["source"],
                "why": "most saturated colour in the code"}
    return None
