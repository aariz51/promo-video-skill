"""Delivery: one folder with everything a client (or the next session) needs.

    promo/deliver/
      videos/                 the rendered films (final quality, plus drafts only if asked)
      CREATIVE_DIRECTION.md   storyboard.md  narration.txt  product-brief.md  creative-prompt.md
      timeline.json  render-config.json  promo.config.json
      TEST_REPORT.md  validation.json
      reference/              Mode B: breakdown.json, motion-spec.json, contact sheets
      remotion/               an editable Remotion project with this film as its default props
      manifest.json           every file, its size, and a sha256 for each video

Refuses to deliver a film whose QA did not pass, and never writes into a folder it did not
create (one without its manifest).
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .config import Workspace, mode
from .util import RENDERER_DIR, PromoError, read_json, write_json

RENDERER_FILES = ["package.json", "package-lock.json", "tsconfig.json", "remotion.config.ts"]
TEXT_ARTIFACTS = ["CREATIVE_DIRECTION.md", "PRODUCT_ANALYSIS.md", "THEME_ANALYSIS.md", "THEME.json", "ASSET_INVENTORY.md",
                  "SCREENSHOT_MANIFEST.json", "storyboard.md", "narration.txt", "product-brief.md",
                  "creative-prompt.md", "timeline.json", "render-config.json", "promo.config.json", "TEST_REPORT.md"]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _place(src: Path, dst: Path) -> None:
    """Hard-link when possible (same disk, no extra space), copy otherwise."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        dst.hardlink_to(src)
    except OSError:
        shutil.copy2(src, dst)


def eject(ws: Workspace, dest: Path) -> Path:
    """Copy the renderer as a standalone, editable project whose default film is this one."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(RENDERER_DIR / "src", dest / "src")
    for name in RENDERER_FILES:
        shutil.copy2(RENDERER_DIR / name, dest / name)
    props = ws.root / "build" / "render-props.json"
    if not props.exists():
        raise PromoError("nothing has been rendered yet", hint="run `promo render` first")
    shutil.copy2(props, dest / "src" / "sample" / "render-config.json")
    pub = dest / "public"
    shutil.copytree(RENDERER_DIR / "public" / "fonts", pub / "fonts")
    staged = ws.stage
    for f in (staged / "fonts").glob("product.*"):  # the product's own typeface, from THEME.json
        shutil.copy2(f, pub / "fonts" / f.name)
    for sub in ("assets", "audio"):
        if (staged / sub).is_dir():
            shutil.copytree(staged / sub, pub / sub, ignore=shutil.ignore_patterns("vo"))
    (dest / "README.md").write_text(
        "# Editable film\n\nThis Remotion project renders this film. Its default props "
        "(`src/sample/render-config.json`) are the film's compiled timeline; the product's assets and the "
        "audio master are in `public/`.\n\n```bash\nnpm ci\nnpx remotion studio            # edit and preview\n"
        "npx remotion render src/index.ts Promo16x9 out/film.mp4\n```\n\nFor a silent film add `--muted`. "
        "Compositions: Promo16x9, Promo9x16, Promo1x1, PromoStorePortrait, PromoStoreLandscape.\n")
    return dest


def deliver(ws: Workspace, *, out: Path | None = None, include_drafts: bool = False, force: bool = False) -> dict:
    dest = (out or ws.root / "deliver").resolve()
    if dest.exists() and not (dest / "manifest.json").exists() and any(dest.iterdir()):
        raise PromoError(f"{dest} exists and was not created by `promo deliver`; refusing to write into it",
                         hint="choose another folder with --out")
    val_path = ws.qa_dir / "validation.json"
    if not val_path.exists():
        raise PromoError("there is no QA result to deliver", hint="run `promo qa` first")
    val = read_json(val_path)
    if val.get("result") != "PASS" and not force:
        raise PromoError("QA did not pass; a failing film is not delivered", hint=f"read {ws.qa_report}")
    videos = sorted(p for p in ws.out_dir.glob("*.mp4") if include_drafts or not p.stem.endswith("-draft"))
    if not videos:
        raise PromoError("no final-quality film to deliver", hint="render with `--quality final`, or pass --drafts")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    files = []
    for v in videos:
        _place(v, dest / "videos" / v.name)
        files.append({"path": f"videos/{v.name}", "bytes": v.stat().st_size, "sha256": _sha256(v)})
    for name in TEXT_ARTIFACTS:
        src = ws.root / name
        if src.exists():
            shutil.copy2(src, dest / name)
            files.append({"path": name, "bytes": src.stat().st_size})
    shutil.copy2(val_path, dest / "validation.json")
    files.append({"path": "validation.json", "bytes": val_path.stat().st_size})
    if ws.screenshot_manifest.exists():
        # The selected genuine screens (and any illustration the film used), named by manifest id.
        used = {sid for sc in read_json(ws.render_config).get("scenes", []) for sid in (sc.get("shots") or [])} \
            if ws.render_config.exists() else set()
        for shot in read_json(ws.screenshot_manifest).get("screenshots", []):
            src = ws.root / shot["path"]
            if (shot.get("selected") or shot["id"] in used) and src.is_file():
                dst = dest / "screenshots" / f"{shot['id']}{src.suffix}"
                _place(src, dst)
                files.append({"path": f"screenshots/{dst.name}", "bytes": src.stat().st_size, "source": shot["source"],
                              "usedInFilm": shot["id"] in used})
    if mode(ws.config()) == "reference" and ws.reference_dir.is_dir():
        for name in ("breakdown.json", "motion-spec.json"):
            if (ws.reference_dir / name).exists():
                _place(ws.reference_dir / name, dest / "reference" / name)
                files.append({"path": f"reference/{name}", "bytes": (ws.reference_dir / name).stat().st_size})
        for sheet in sorted((ws.reference_dir / "sheets").glob("*.jpg")):
            _place(sheet, dest / "reference" / "sheets" / sheet.name)
            files.append({"path": f"reference/sheets/{sheet.name}", "bytes": sheet.stat().st_size})
    eject(ws, dest / "remotion")
    files.append({"path": "remotion/", "note": "editable Remotion project (npm ci; npx remotion studio)"})
    manifest = {"product": val.get("product"), "mode": mode(ws.config()), "qa": val.get("result"),
                "audio": val.get("audioPolicy"), "files": files}
    write_json(dest / "manifest.json", manifest)
    return manifest
