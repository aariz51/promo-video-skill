"""Theme discovery: the product's own design system, from its code and its real screens.

Reads design tokens wherever the stack keeps them (CSS custom properties with their light /
dark context, Tailwind config and v4 `@theme`, Flutter `ThemeData`, iOS colour sets,
Android `colors.xml`), fonts (`@font-face`, `next/font`, font files, Flutter `pubspec`), and
the interface language (radii, shadows, blur, gradients, borders, text casing and tracking,
icon and motion libraries). Screenshots of the running product corroborate the palette by
sampling pixels. Nothing is guessed: a role with no evidence is recorded as unknown.

`discover()` returns the THEME.json document:

  original   the product's theme, per mode, every value with its source and whether it
             was read from a token (`verified`) or sampled from pixels (`estimated`)
  promo      how the film uses it: ground, ink, accent, font, as the renderer consumes them
  motion     filled in Mode B with a pointer to the reference's measured motion language
"""
from __future__ import annotations

import colorsys
import json
import math
import re
from collections import Counter
from pathlib import Path

from .analyzer import _is_secret, walk

STYLE_EXT = {".css", ".scss", ".sass", ".less", ".pcss"}
MARKUP_EXT = {".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte", ".astro", ".mdx"}
FONT_EXT = {".ttf", ".otf", ".woff", ".woff2"}
MAX_BYTES = 600_000

ROLES = [  # role, name pattern (first match wins, so specific roles come first)
    ("text", r"(^|[-_.])(foreground|fg|text|ink|on[-_]?background|on[-_]?surface|label)($|[-_.])"),
    ("border", r"(^|[-_.])(border|line|stroke|divider|outline|separator)($|[-_.])"),
    ("error", r"(^|[-_.])(error|danger|destructive|red)($|[-_.])"),
    ("success", r"(^|[-_.])(success|positive|green)($|[-_.])"),
    ("warning", r"(^|[-_.])(warning|caution|amber|yellow)($|[-_.])"),
    ("info", r"(^|[-_.])(info|notice)($|[-_.])"),
    ("primary", r"(^|[-_.])(primary|brand|seed)($|[-_.])"),
    ("secondary", r"(^|[-_.])(secondary)($|[-_.])"),
    ("accent", r"(^|[-_.])(accent|highlight|tertiary)($|[-_.])"),
    ("surface", r"(^|[-_.])(surface|card|panel|popover|sheet|elevated|muted|container)($|[-_.])"),
    ("background", r"(^|[-_.])(background|bg|paper|canvas|scaffold|base|page|backdrop)($|[-_.])"),
]
SKIP_NAME = re.compile(r"(foreground|text|on)[-_]?(primary|secondary|accent)|(primary|secondary|accent)[-_]?(foreground|fg|text)", re.I)
DARK_SELECTOR = re.compile(r"\.dark\b|\[data-theme=['\"]?dark|\[data-mode=['\"]?dark|\.theme-dark|:root\.dark", re.I)
LIGHT_SELECTOR = re.compile(r"^\s*(:root|html|body|\.light|\[data-theme=['\"]?light['\"]?\])\s*$", re.I)


# ── colour parsing ─────────────────────────────────────────────────────────────────

def _hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in (r, g, b))


def _oklch(l: float, c: float, h: float) -> tuple[float, float, float]:
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_, m_, s_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3, (l - 0.1055613458 * a - 0.0638541728 * b) ** 3, \
        (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    return tuple((12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055) for x in lin)


def _num(s: str, scale: float = 1.0) -> float:
    s = s.strip()
    return float(s[:-1]) / 100 if s.endswith("%") else float(s) / scale


def parse_color(value: str) -> str | None:
    """CSS colour (hex, rgb[a], hsl[a], oklch, or a bare shadcn-style HSL triplet) → #RRGGBB."""
    v = value.strip().lower().rstrip(";").strip()
    m = re.fullmatch(r"#([0-9a-f]{3,8})", v)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h[:3])
        return "#" + h[:6].upper() if len(h) >= 6 else None
    m = re.fullmatch(r"0x([0-9a-f]{8})", v)  # Flutter ARGB
    if m:
        return "#" + m.group(1)[2:].upper()
    m = re.fullmatch(r"rgba?\(\s*([\d.%]+)[\s,]+([\d.%]+)[\s,]+([\d.%]+).*\)", v)
    if m:
        return _hex(*(_num(x, 255) for x in m.groups()))
    m = re.fullmatch(r"(?:hsla?\(\s*)?([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%(?:\s*[,/][^)]*)?\)?", v)
    if m:
        h, s, l = float(m.group(1)) / 360, float(m.group(2)) / 100, float(m.group(3)) / 100
        return _hex(*colorsys.hls_to_rgb(h, l, s))
    m = re.fullmatch(r"oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)(?:deg)?\s*(?:/[^)]*)?\)", v)
    if m:
        l = _num(m.group(1)) if m.group(1).endswith("%") else float(m.group(1))
        return _hex(*_oklch(l, float(m.group(2)), float(m.group(3))))
    return None


def rgb(hexv: str) -> tuple[float, float, float]:
    h = hexv.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminance(hexv: str) -> float:
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(hexv))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def saturation(hexv: str) -> float:
    r, g, b = rgb(hexv)
    hi, lo = max(r, g, b), min(r, g, b)
    return (hi - lo) / hi if hi else 0.0


def mix(a: str, b: str, t: float) -> str:
    """t=0 → a, t=1 → b."""
    return _hex(*((1 - t) * x + t * y for x, y in zip(rgb(a), rgb(b))))


def role_of(name: str) -> str | None:
    # camelCase (Dart, Swift, Kotlin) → kebab, so scaffoldBackgroundColor reads as background
    n = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", name.lstrip("-$@")).lower()
    if SKIP_NAME.search(n):
        return "text"  # "primary-foreground": text drawn on the primary colour
    for role, pat in ROLES:
        if re.search(pat, n):
            return role
    return None


# ── token collection ───────────────────────────────────────────────────────────────

def _files(root: Path, exts: set[str]):
    for p in walk(root):
        if p.suffix.lower() in exts and not _is_secret(p.name):
            try:
                if p.stat().st_size <= MAX_BYTES:
                    yield p
            except OSError:
                continue


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _css_blocks(css: str):
    """(selector, body, offset, in_dark_media) for every rule, including those nested in @media."""
    css = re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), css, flags=re.S)
    for m in re.finditer(r"@media[^{]*prefers-color-scheme\s*:\s*dark[^{]*\{", css):
        depth, i = 1, m.end()
        while i < len(css) and depth:
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        inner = css[m.end():i - 1]
        for b in re.finditer(r"([^{}]+)\{([^{}]*)\}", inner):
            yield b.group(1).strip(), b.group(2), m.end() + b.start(2), True
        css = css[:m.start()] + " " * (i - m.start()) + css[i:]
    for b in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = b.group(1).strip()
        if sel.startswith("@media") or sel.startswith("@keyframes"):
            continue
        yield sel.split("}")[-1].strip(), b.group(2), b.start(2), False


def collect_tokens(root: Path) -> list[dict]:
    """Every colour token the product defines, with its name, mode and source line."""
    out: list[dict] = []

    def add(name, value, mode, src, kind):
        hexv = parse_color(value)
        if hexv:
            out.append({"name": name, "value": hexv, "raw": value.strip()[:60], "mode": mode,
                        "source": src, "kind": kind, "role": role_of(name)})

    for p in _files(root, STYLE_EXT):
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for sel, body, off, dark_media in _css_blocks(text):
            if sel.startswith("@theme"):
                mode = "light"
            elif dark_media or DARK_SELECTOR.search(sel):
                mode = "dark"
            elif LIGHT_SELECTOR.match(sel) or sel.startswith(":root"):
                mode = "light"
            else:
                continue  # component styles are evidence for the UI language, not the palette
            for d in re.finditer(r"(--[\w-]+)\s*:\s*([^;}]+)", body):
                add(d.group(1), d.group(2), mode, f"{rel}:{_line_of(text, off + d.start())}", "css-var")
            for d in re.finditer(r"(?<![-\w])(background(?:-color)?|color|border-color)\s*:\s*([^;}]+)", body):
                if "var(" not in d.group(2):
                    add(d.group(1).replace("background-color", "background").replace("color", "text")
                        if d.group(1) == "color" else d.group(1), d.group(2), mode,
                        f"{rel}:{_line_of(text, off + d.start())}", "css-rule")
    for p in _files(root, {".js", ".ts", ".cjs", ".mjs"}):
        if not re.match(r"tailwind\.config\.", p.name):
            continue
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for d in re.finditer(r"['\"]?([\w-]+)['\"]?\s*:\s*['\"](#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)|hsla?\([^)]*\))['\"]", text):
            add(d.group(1), d.group(2), "light", f"{rel}:{_line_of(text, d.start())}", "tailwind")
    for p in _files(root, {".dart"}):
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for d in re.finditer(r"(\w+)\s*:\s*(?:const\s+)?Color\(\s*0x([0-9A-Fa-f]{8})\s*\)", text):
            ctx = text[max(0, d.start() - 600):d.start()]
            dark = bool(re.search(r"Brightness\.dark|darkTheme|dark\w*\s*=", ctx)) and \
                ctx.rfind("Brightness.dark") > ctx.rfind("Brightness.light")
            add(d.group(1), "0x" + d.group(2), "dark" if dark else "light", f"{rel}:{_line_of(text, d.start())}", "flutter")
        for d in re.finditer(r"(?:const\s+)?(\w+)\s*=\s*(?:const\s+)?Color\(\s*0x([0-9A-Fa-f]{8})\s*\)", text):
            add(d.group(1), "0x" + d.group(2), "dark" if "dark" in d.group(1).lower() else "light",
                f"{rel}:{_line_of(text, d.start())}", "flutter")
    for p in walk(root):
        if p.name != "Contents.json" or not p.parent.name.endswith(".colorset"):
            continue
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        name = p.parent.name[:-len(".colorset")]
        for c in data.get("colors", []):
            comps = (c.get("color") or {}).get("components") or {}
            try:
                vals = [comps[k] for k in ("red", "green", "blue")]
                vals = [int(v, 16) / 255 if str(v).startswith("0x") else (float(v) if float(v) <= 1 else float(v) / 255)
                        for v in vals]
            except (KeyError, ValueError):
                continue
            dark = any(a.get("value") == "dark" for a in c.get("appearances", []))
            out.append({"name": name, "value": _hex(*vals), "raw": json.dumps(comps)[:60], "mode": "dark" if dark else "light",
                        "source": p.relative_to(root).as_posix(), "kind": "ios-colorset", "role": role_of(name)})
    for p in walk(root):
        if p.name == "colors.xml" and "res" in p.parts:
            rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
            mode = "dark" if any(part.startswith("values-night") for part in p.parts) else "light"
            for d in re.finditer(r'<color name="([^"]+)">\s*(#[0-9A-Fa-f]{6,8})\s*</color>', text):
                v = d.group(2)
                v = "#" + v[-6:] if len(v) == 9 else v  # #AARRGGBB
                add(d.group(1), v, mode, f"{rel}:{_line_of(text, d.start())}", "android")
    return out


# ── fonts and interface language ───────────────────────────────────────────────────

GENERIC = {"sans-serif", "serif", "monospace", "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
           "-apple-system", "blinkmacsystemfont", "inherit", "initial", "var", "cursive", "fantasy", "emoji"}


def collect_fonts(root: Path) -> dict:
    families: Counter = Counter()
    sources: dict[str, str] = {}
    faces: list[dict] = []
    for p in _files(root, STYLE_EXT):
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for m in re.finditer(r"@font-face\s*\{([^}]*)\}", text):
            fam = re.search(r"font-family\s*:\s*['\"]?([^;'\"]+)", m.group(1))
            src = re.search(r"url\(['\"]?([^)'\"]+)", m.group(1))
            if fam:
                faces.append({"family": fam.group(1).strip(), "url": src.group(1) if src else None,
                              "source": f"{rel}:{_line_of(text, m.start())}"})
        for m in re.finditer(r"font-family\s*:\s*([^;}]+)", text):
            first = m.group(1).split(",")[0].strip().strip("'\"")
            if first.lower() not in GENERIC and not first.startswith("var("):
                families[first] += 1
                sources.setdefault(first, f"{rel}:{_line_of(text, m.start())}")
    for p in _files(root, MARKUP_EXT | {".js", ".ts"}):
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for m in re.finditer(r"import\s*\{([^}]+)\}\s*from\s*['\"](?:next/font/google|geist/font[^'\"]*)['\"]", text):
            for name in m.group(1).split(","):
                fam = name.strip().split(" as ")[0].replace("_", " ")
                if fam:
                    families[fam] += 3
                    sources.setdefault(fam, f"{rel}:{_line_of(text, m.start())} (next/font)")
        if re.match(r"tailwind\.config\.", p.name):
            for m in re.finditer(r"(sans|serif|display|heading|body)\s*:\s*\[\s*['\"]([^'\"]+)['\"]", text):
                families[m.group(2)] += 2
                sources.setdefault(m.group(2), f"{rel}:{_line_of(text, m.start())} (tailwind {m.group(1)})")
    pub = root / "pubspec.yaml"
    if pub.is_file():
        # YAML comments are not declarations (flutter create ships commented-out font examples).
        text = re.sub(r"(?m)^\s*#.*$", "", pub.read_text(errors="replace"))
        for m in re.finditer(r"-\s*family\s*:\s*([^\n#]+)", text):
            families[m.group(1).strip()] += 3
            sources.setdefault(m.group(1).strip(), f"pubspec.yaml:{_line_of(text, m.start())}")
    files = [p.relative_to(root).as_posix() for p in walk(root) if p.suffix.lower() in FONT_EXT]
    for f in faces:
        families[f["family"]] += 2
        sources.setdefault(f["family"], f["source"])

    def file_for(fam: str) -> str | None:
        for face in faces:
            if face["family"].lower() == fam.lower() and face["url"]:
                tail = Path(face["url"]).name
                hit = next((x for x in files if x.endswith("/" + tail) or x == tail), None)
                if hit:
                    return hit
        key = re.sub(r"[^a-z0-9]", "", fam.lower())
        return next((x for x in files if re.sub(r"[^a-z0-9]", "", Path(x).stem.lower()).startswith(key)), None)

    ranked = [{"family": fam, "uses": n, "source": sources.get(fam), "file": file_for(fam)}
              for fam, n in families.most_common(6)]
    return {"families": ranked, "fontFiles": files[:20], "faces": faces[:10]}


TAILWIND_CLASS = re.compile(r"\b(rounded(?:-[a-z0-9]+)?|shadow(?:-[a-z0-9]+)?|backdrop-blur(?:-[a-z0-9]+)?|"
                            r"bg-gradient-to-[a-z]+|uppercase|tracking-[a-z]+|font-(?:bold|semibold|medium|black|light)|"
                            r"border(?:-\d)?|leading-[a-z0-9]+)\b")


def collect_ui(root: Path, scan: dict | None) -> dict:
    css_radius: Counter = Counter()
    counts: Counter = Counter()
    classes: Counter = Counter()
    evidence: dict[str, str] = {}
    for p in _files(root, STYLE_EXT):
        rel, text = p.relative_to(root).as_posix(), p.read_text(errors="replace")
        for m in re.finditer(r"(?:border-radius|--radius[\w-]*)\s*:\s*([\d.]+(?:px|rem|em))", text):
            css_radius[m.group(1)] += 1
            evidence.setdefault("radius", f"{rel}:{_line_of(text, m.start())}")
        for key, pat in (("shadow", r"box-shadow\s*:"), ("blur", r"backdrop-filter\s*:\s*blur"),
                         ("gradient", r"(linear|radial)-gradient\("), ("uppercase", r"text-transform\s*:\s*uppercase"),
                         ("tracking", r"letter-spacing\s*:"), ("transition", r"\btransition\s*:"),
                         ("animation", r"\banimation\s*:|@keyframes"), ("border", r"\bborder\s*:\s*\d")):
            n = len(re.findall(pat, text, re.I))
            if n:
                counts[key] += n
                evidence.setdefault(key, rel)
    for p in _files(root, MARKUP_EXT):
        for m in TAILWIND_CLASS.finditer(p.read_text(errors="replace")):
            classes[m.group(1)] += 1
    deps = set()
    for man in ((scan or {}).get("manifests") or {}).values():
        deps.update(man.get("dependencies") or [])
    icons = sorted(d for d in deps if re.search(r"lucide|heroicons|react-icons|phosphor|@mui/icons|tabler|feather|font-?awesome", d))
    motion = sorted(d for d in deps if re.search(r"framer-motion|^motion$|gsap|@react-spring|lottie|animejs|rive", d))
    ui_kits = sorted(d for d in deps if re.search(r"@radix-ui|shadcn|@mui|@chakra|antd|@mantine|daisyui|headlessui", d))
    radius = css_radius.most_common(1)[0][0] if css_radius else None
    if not radius:
        tw = [c for c in classes if c.startswith("rounded")]
        radius = max(tw, key=lambda c: classes[c]) if tw else None
    return {"radius": radius, "radii": dict(css_radius.most_common(5)), "counts": dict(counts),
            "tailwindClasses": dict(classes.most_common(15)), "iconLibraries": icons, "motionLibraries": motion,
            "uiKits": ui_kits, "evidence": evidence}


# ── pixels ─────────────────────────────────────────────────────────────────────────

def sample_screenshot(path: Path) -> dict | None:
    """Dominant (background) colour and the most saturated common colour of a real screen."""
    from .reference import _frame_at
    raw = _frame_at(path, 0, 320, 180)  # fine enough that buttons keep their true colour
    if raw is None:
        return None
    bins: Counter = Counter()
    for i in range(0, len(raw), 3):
        bins[(raw[i] >> 3, raw[i + 1] >> 3, raw[i + 2] >> 3)] += 1
    total = sum(bins.values())
    hexes = [(_hex(*((c * 8 + 4) / 255 for c in k)), n / total) for k, n in bins.most_common(40)]
    bg = hexes[0]
    allbins = [(_hex(*((c * 8 + 4) / 255 for c in k)), n / total) for k, n in bins.most_common()]
    vivid = [(h, s) for h, s in allbins if saturation(h) > 0.35 and 0.05 < luminance(h) < 0.8 and s > 0.0008]
    return {"dominant": bg[0], "dominantShare": round(bg[1], 3), "vivid": vivid[0][0] if vivid else None}


def _near(a: str, b: str) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(rgb(a), rgb(b)))) / math.sqrt(3)


# ── assembly ───────────────────────────────────────────────────────────────────────

def _palette(tokens: list[dict], mode: str) -> dict:
    out: dict[str, dict] = {}
    ordered = sorted((t for t in tokens if t["mode"] == mode and t["role"]),
                     key=lambda t: (t["kind"] not in ("css-var", "tailwind", "flutter", "ios-colorset", "android"),))
    for t in ordered:
        out.setdefault(t["role"], {"value": t["value"], "source": t["source"], "token": t["name"], "verified": True})
    return out


def classify(original: dict, ui: dict, fonts: dict, scan: dict | None) -> list[dict]:
    labels = []
    default = original["modes"].get(original["defaultMode"], {})
    bg = (default.get("background") or {}).get("value")
    counts, classes = ui["counts"], ui["tailwindClasses"]
    frameworks = set((scan or {}).get("frameworks") or [])
    blur = counts.get("blur", 0) + sum(n for c, n in classes.items() if c.startswith("backdrop-blur"))
    if bg and luminance(bg) < 0.06:
        labels.append({"label": "premium dark interface", "evidence": f"default background {bg} ({default['background']['source']})"})
    if blur >= 3:
        labels.append({"label": "glassmorphism", "evidence": f"{blur} backdrop blurs ({ui['evidence'].get('blur', 'markup classes')})"})
    vivid = {t["value"] for m in original["modes"].values() for t in m.values() if saturation(t["value"]) > 0.45}
    big = ui["radius"] and re.match(r"([\d.]+)(px|rem)", ui["radius"] or "")
    radius_px = (float(big.group(1)) * (16 if big.group(2) == "rem" else 1)) if big else 0
    if len(vivid) >= 4 and radius_px >= 16:
        labels.append({"label": "playful", "evidence": f"{len(vivid)} saturated colours, {ui['radius']} radius"})
    serif = [f for f in fonts["families"] if re.search(r"serif|garamond|georgia|playfair|merriweather|times", f["family"], re.I)
             and not re.search(r"sans", f["family"], re.I)]
    if bg and luminance(bg) > 0.7 and (serif or len(vivid) <= 1):
        labels.append({"label": "minimal and editorial", "evidence": f"light background {bg}"
                       + (f", serif {serif[0]['family']}" if serif else ", restrained palette")})
    semantic = {t for m in original["modes"].values() for t in m}
    if ui["uiKits"] or (classes and "Tailwind CSS" in frameworks) or {"background", "text", "primary", "surface", "border"} <= semantic:
        labels.append({"label": "modern SaaS", "evidence": ", ".join(ui["uiKits"]) or (
            "Tailwind utility classes" if classes else "a semantic token set (background / foreground / primary / card / border)")})
    if bg and luminance(bg) > 0.7 and radius_px >= 12:
        labels.append({"label": "soft and approachable", "evidence": f"light ground {bg}, {ui['radius']} corners "
                       f"({ui['evidence'].get('radius', 'styles')})"})
    if any("mui" in k for k in ui["uiKits"]) or "Flutter" in frameworks:
        labels.append({"label": "Material-inspired", "evidence": "Material components (MUI / Flutter)"})
    if not labels:
        labels.append({"label": "unclassified", "evidence": "too little styling evidence to name a design language"})
    return labels


def adapt(original: dict, fonts: dict) -> dict:
    """The film's use of the theme: the renderer reads exactly these values."""
    mode = original["defaultMode"]
    pal = original["modes"].get(mode, {})
    notes = []

    def val(*roles):
        for r in roles:
            if r in pal:
                return pal[r]["value"]
        return None

    ground = val("background") or (original.get("sampled") or {}).get("dominant")
    if ground is None:
        ground = "#0B0C0F"
        notes.append("no background colour in the product's code or screens; the default graphite ground is used")
    dark = luminance(ground) < 0.18
    ink = val("text") or ("#F4F1EA" if dark else "#16171A")
    if contrast(ink, ground) < 4.5:
        fixed = "#FFFFFF" if dark else "#111111"
        notes.append(f"text {ink} on {ground} is below 4.5:1 for video; {fixed} is used for on-screen type")
        ink = fixed
    accent = val("primary", "accent", "secondary")
    if accent is None:
        accent = (original.get("sampled") or {}).get("vivid")
        if accent:
            notes.append(f"accent {accent} sampled from the product's screens (no primary token)")
    if accent is None:
        accent = "#6E9BFF"
        notes.append("no brand colour found; the neutral default accent is used and is not presented as the brand's")
    surface = val("surface")
    border = val("border")
    family = next((f for f in fonts["families"] if f["file"]), None)
    head = fonts["families"][0]["family"] if fonts["families"] else None
    if head and (not family or family["family"] != head):
        notes.append(f"the product's font {head} has no font file in the repository; Inter is used instead")
    elif not head:
        notes.append("the product declares no font of its own (platform default); Inter is used for the film's type")
    return {
        "mode": mode, "preset": "graphite" if dark else "paper", "dark": dark,
        "ground": ground, "ground2": surface if surface and surface != ground else mix(ground, ink, 0.06),
        "ink": ink, "inkSoft": mix(ink, ground, 0.42), "line": border or mix(ink, ground, 0.84),
        "accent": accent, "fontHead": family["family"] if family else "Inter",
        "fontFile": family["file"] if family else None,
        "allowed": ["soft light pools in the accent", "depth and parallax", "subtle grain and vignette"],
        "notes": notes,
    }


def discover(root: str | Path, scan: dict | None = None, screenshots: list[Path] | None = None) -> dict:
    root = Path(root)
    tokens = collect_tokens(root)
    fonts = collect_fonts(root)
    ui = collect_ui(root, scan)
    modes = {m: _palette(tokens, m) for m in ("light", "dark")}
    modes = {m: p for m, p in modes.items() if p}
    samples = [s for s in (sample_screenshot(p) for p in (screenshots or [])[:6]) if s]
    sampled = None
    if samples:
        dom = Counter(s["dominant"] for s in samples).most_common(1)[0][0]
        vivid = next((s["vivid"] for s in samples if s["vivid"]), None)
        sampled = {"dominant": dom, "vivid": vivid, "screens": len(samples)}
    # The default mode is the one the real screens show; without screens, the light (root) tokens.
    if sampled and modes:
        default = min(modes, key=lambda m: _near(modes[m].get("background", {}).get("value", sampled["dominant"]), sampled["dominant"]))
    else:
        default = "light" if "light" in modes else ("dark" if modes else "light")
    if sampled and default in modes and "background" not in modes[default]:
        modes[default]["background"] = {"value": sampled["dominant"], "source": "sampled from captured screens",
                                        "verified": False, "estimated": True}
    corroboration = []
    if sampled and default in modes and modes[default].get("background", {}).get("verified"):
        tok = modes[default]["background"]["value"]
        d = _near(tok, sampled["dominant"])
        corroboration.append({"role": "background", "token": tok, "sampled": sampled["dominant"],
                              "agrees": d < 0.08, "distance": round(d, 3)})
    if sampled and sampled["vivid"] and default in modes and "primary" in modes[default]:
        tok = modes[default]["primary"]["value"]
        d = _near(tok, sampled["vivid"])
        corroboration.append({"role": "primary", "token": tok, "sampled": sampled["vivid"], "agrees": d < 0.12,
                              "distance": round(d, 3)})
    required = ["primary", "background", "surface", "text", "border"]
    unknown = [f"{m}.{r}" for m in (modes or {"light": {}}) for r in required if r not in modes.get(m, {})]
    gradients = ui["counts"].get("gradient", 0) + sum(n for c, n in ui["tailwindClasses"].items() if c.startswith("bg-gradient"))
    original = {"modes": modes, "defaultMode": default, "hasDarkMode": "dark" in modes, "sampled": sampled,
                "corroboration": corroboration, "tokens": len(tokens), "gradients": gradients,
                "unknown": unknown}
    original["classification"] = classify(original, ui, fonts, scan)
    return {"version": 1, "original": original, "typography": fonts, "ui": ui,
            "promo": adapt(original, fonts), "motion": None,
            "tokenList": tokens[:120]}
