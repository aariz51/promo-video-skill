#!/usr/bin/env python3
"""Generate the brand-neutral placeholder assets the template ships with.

The template must render the moment it is cloned — before anyone has supplied a
single screenshot. So `public/app-screens/` and `public/logo/` ship with
generated stand-ins, and this script is what generates them.

They are deliberately plain: a generic light UI with a slot label, so a frame
render obviously reads as "your screen goes here" and never as a real product.
Replace them with real PNGs and point `src/theme.ts` -> `screens` / `LOGO` at
your files; nothing else needs to change.

    python3 scripts/make_placeholders.py

Requires Pillow (`pip install pillow`). Only needed to REGENERATE the assets —
the generated PNGs are committed, so a normal user never runs this.
"""
import os

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - dependency guidance
    raise SystemExit(
        "Pillow is required to regenerate placeholders.\n"
        "  pip install pillow\n"
        "You only need this if you are regenerating the committed placeholder PNGs."
    )

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENS_DIR = os.path.join(ROOT, "public", "app-screens")
LOGO_DIR = os.path.join(ROOT, "public", "logo")

# Matches SCREEN_W / SCREEN_H in src/theme.ts (portrait phone capture).
W, H = 1080, 2340

# Neutral slate/indigo. Intentionally NOT a brand palette — these are stand-ins.
INK = (30, 34, 48)
INK_SOFT = (122, 130, 150)
LINE = (226, 230, 238)
CARD = (255, 255, 255)
BG = (245, 247, 251)
ACCENT = (99, 102, 241)
ACCENT_SOFT = (224, 226, 255)

# The seven slots the shipped scenes actually reference (see src/theme.ts).
SCREENS = [
    ("01-home.png", "HOME"),
    ("02-detail.png", "DETAIL"),
    ("03-search.png", "SEARCH"),
    ("04-library.png", "LIBRARY"),
    ("05-profile.png", "PROFILE"),
    ("06-settings.png", "SETTINGS"),
    ("07-result.png", "RESULT"),
]


def rounded(draw, box, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_block(draw, x, y, w, h, color, radius=None):
    """A grey bar standing in for a line of text — keeps the stand-in wordless."""
    rounded(draw, (x, y, x + w, y + h), radius if radius is not None else h // 2, color)


def draw_screen(path, label):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ── status bar ────────────────────────────────────────────────────────────
    text_block(d, 90, 70, 150, 26, INK_SOFT)
    for i, bw in enumerate((34, 34, 52)):
        x = W - 90 - bw - i * 60
        text_block(d, x, 70, bw, 26, INK_SOFT)

    # ── header: title + avatar ────────────────────────────────────────────────
    text_block(d, 90, 190, 420, 58, INK)
    text_block(d, 90, 276, 300, 30, INK_SOFT)
    d.ellipse((W - 90 - 108, 190, W - 90, 298), fill=ACCENT_SOFT)

    # ── hero card, with the slot label ────────────────────────────────────────
    hero = (72, 380, W - 72, 980)
    rounded(d, hero, 48, CARD, LINE, 3)
    rounded(d, (132, 440, 132 + 96, 440 + 96), 28, ACCENT_SOFT)
    text_block(d, 132, 580, 560, 44, INK)
    text_block(d, 132, 648, 400, 30, INK_SOFT)
    rounded(d, (132, 730, 132 + 320, 730 + 78), 39, ACCENT)

    # The one piece of real text: which slot this is.
    tw = d.textlength(label)
    d.text(((W - tw) / 2, 880), label, fill=INK_SOFT)

    # ── list rows ─────────────────────────────────────────────────────────────
    y = 1060
    for _ in range(5):
        rounded(d, (72, y, W - 72, y + 210), 40, CARD, LINE, 3)
        rounded(d, (128, y + 52, 128 + 106, y + 52 + 106), 30, ACCENT_SOFT)
        text_block(d, 268, y + 68, 470, 36, INK)
        text_block(d, 268, y + 124, 330, 28, INK_SOFT)
        y += 238

    # ── bottom tab bar ────────────────────────────────────────────────────────
    bar_top = H - 230
    rounded(d, (0, bar_top, W, H), 0, CARD)
    d.line((0, bar_top, W, bar_top), fill=LINE, width=3)
    for i in range(4):
        cx = W * (2 * i + 1) / 8
        color = ACCENT if i == 0 else LINE
        rounded(d, (cx - 34, bar_top + 56, cx + 34, bar_top + 124), 22, color)

    img.save(path, "PNG")
    return path


def draw_logo(path):
    """A neutral rounded-tile mark so the logo-lockup scene has something real."""
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rounded(d, (0, 0, size, size), int(size * 0.22), ACCENT)

    # A simple geometric glyph — no letters, so it reads as a placeholder mark.
    cx, cy, r = size / 2, size / 2, size * 0.22
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255), width=int(size * 0.045))
    d.rounded_rectangle(
        (cx - size * 0.035, cy - r * 1.75, cx + size * 0.035, cy - r * 0.55),
        radius=size * 0.035,
        fill=(255, 255, 255),
    )
    img.save(path, "PNG")
    return path


def main():
    os.makedirs(SCREENS_DIR, exist_ok=True)
    os.makedirs(LOGO_DIR, exist_ok=True)

    for filename, label in SCREENS:
        print("wrote", draw_screen(os.path.join(SCREENS_DIR, filename), label))
    print("wrote", draw_logo(os.path.join(LOGO_DIR, "app-logo.png")))
    print(
        "\nPlaceholders regenerated. Replace them with your real screenshots and "
        "update `screens` / `LOGO` in src/theme.ts."
    )


if __name__ == "__main__":
    main()
