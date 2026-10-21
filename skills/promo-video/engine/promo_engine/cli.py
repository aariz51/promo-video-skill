"""`promo`: the creative compiler's command line.

  PRODUCT REPOSITORY ─ scan ─┐
  OPTIONAL YOUTUBE ── watch ─┤→ (agent writes brief / inspiration prompt) ─ check
                             └→ adapt → (agent completes creative prompt, writes timeline) ─ check
                                → compile → voice → audio → render → qa     (or: build)

Every step reads and writes files in the workspace (default ./promo) so each stage can be
inspected, re-run or edited by hand.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from . import adapter, analyzer, artifacts, audio, capture, qa, render, timeline, voiceover, watcher
from .config import ASPECTS, QUALITY, Workspace, init_workspace
from .util import RENDERER_DIR, PromoError, Report, free_gb, read_json, write_json
from .youtube import parse_youtube_url


def _ws(args) -> Workspace:
    return Workspace.at(args.workspace)


def _print_report(rep: Report, ok_msg: str) -> int:
    if rep.issues:
        print(rep.summary())
    if rep.ok:
        print(ok_msg)
        return 0
    print(f"\n{len(rep.errors)} error(s). Fix them and re-run.")
    return 2


def cmd_doctor(args) -> int:
    rows = []
    for tool in ("node", "npx", "ffmpeg", "ffprobe", "yt-dlp"):
        rows.append((tool, bool(shutil.which(tool)), shutil.which(tool) or "missing"))
    rows.append(("renderer deps", (RENDERER_DIR / "node_modules" / "@remotion" / "cli").is_dir(),
                 "installed" if (RENDERER_DIR / "node_modules").is_dir() else "run `npm ci` in renderer/ (auto on first render)"))
    try:
        rows.append(("watch skill", True, str(watcher.find_watch_skill())))
    except PromoError as exc:
        rows.append(("watch skill", False, f"{exc} (only needed with an inspiration video)"))
    rows.append(("voice: openrouter", bool(os.environ.get("OPENROUTER_API_KEY")),
                 "OPENROUTER_API_KEY set" if os.environ.get("OPENROUTER_API_KEY") else "OPENROUTER_API_KEY not set"))
    rows.append(("voice: say", bool(shutil.which("say")), "macOS say" if shutil.which("say") else "not macOS"))
    try:
        rows.append(("chrome (capture)", True, capture.find_chrome()))
    except PromoError:
        rows.append(("chrome (capture)", False, "not found (capture is optional)"))
    gb = free_gb(Path.cwd())
    rows.append(("disk", gb >= 1.5, f"{gb:.1f} GB free (renders need ~1.5 GB)"))
    for name, ok, note in rows:
        print(f"  {'✓' if ok else '✗'} {name:<18} {note}")
    essential = {"node", "npx", "ffmpeg", "ffprobe"}
    return 0 if all(ok for n, ok, _ in rows if n in essential) else 1


def cmd_init(args) -> int:
    ws = _ws(args)
    url = None
    if args.inspiration and args.inspiration.lower() != "none":
        url = parse_youtube_url(args.inspiration).url
    path = init_workspace(ws, product_root=Path(args.product), name=args.name,
                          inspiration_url=url if args.inspiration else None)
    print(f"Workspace ready: {ws.root}\nConfig: {path}")
    print("Workflow:", "inspiration → " + url if url else "master creative framework (no inspiration)")
    return 0


def cmd_scan(args) -> int:
    ws = _ws(args)
    data = analyzer.scan(ws.product_root, exclude=ws.root)
    write_json(ws.scan, data)
    print(analyzer.summarize(data, root=ws.product_root))
    print(f"\nWrote {ws.scan}")
    return 0


def cmd_capture(args) -> int:
    ws = _ws(args)
    url, cmd, cwd = args.url, args.cmd, ws.product_root
    if args.launch and ws.scan.exists():
        plan = read_json(ws.scan)["launch"]
        url = url or plan.get("url")
        cmd = cmd or plan.get("command")
        cwd = ws.product_root / (plan.get("cwd") or ".")
    shots = capture.capture(ws, url=url, routes=args.routes, size=args.size, launch=args.launch,
                            launch_cmd=cmd, cwd=cwd)
    for s in shots:
        print(f"  captured {s.relative_to(ws.root)}")
    return 0


def cmd_watch(args) -> int:
    ws = _ws(args)
    ev = watcher.watch(ws, args.url, detail=args.detail)
    print(watcher.evidence_summary(ev))
    print(f"\nEvidence: {ws.evidence}\nRead every frame listed there before writing {ws.inspiration.name}.")
    return 0


def _transcript(ws: Workspace) -> list[str]:
    if not ws.evidence.exists():
        return []
    return [l["text"] for l in read_json(ws.evidence)["transcript"]["lines"]]


def cmd_check(args) -> int:
    ws = _ws(args)
    rep = Report()
    what = args.what
    cfg = ws.config()
    uses_insp = bool(cfg["inspiration"].get("url"))
    if what in ("inspiration", "all") and (what == "inspiration" or uses_insp):
        if not ws.inspiration.exists():
            rep.error(ws.inspiration.name, "missing")
        else:
            ev = read_json(ws.evidence) if ws.evidence.exists() else None
            if ev is None:
                rep.error(ws.inspiration.name, "no watch evidence: run `promo watch <url>` first")
            rep.extend(artifacts.check_inspiration(ws.inspiration.read_text(), ev))
    if what in ("brief", "all"):
        if not ws.brief.exists():
            rep.error(ws.brief.name, "missing")
        else:
            rep.extend(artifacts.check_brief(ws.brief.read_text(), ws.product_root))
    if what in ("creative", "all"):
        if not ws.creative.exists():
            rep.error(ws.creative.name, "missing (run `promo adapt`)")
        else:
            claims = artifacts.parse_claims(ws.brief.read_text()) if ws.brief.exists() else {}
            rules = artifacts.parse_rules(ws.inspiration.read_text()) if uses_insp and ws.inspiration.exists() else []
            rep.extend(artifacts.check_creative(ws.creative.read_text(), claims=claims,
                                                source="inspiration" if uses_insp else "framework",
                                                rules=rules, transcript=_transcript(ws)))
    if what in ("timeline", "all"):
        if not ws.timeline.exists():
            rep.error(ws.timeline.name, "missing")
        else:
            claims = artifacts.parse_claims(ws.brief.read_text()) if ws.brief.exists() else {}
            rep.extend(timeline.validate(read_json(ws.timeline), ws, cfg, claims))
            tl = read_json(ws.timeline)
            if uses_insp:
                said = " ".join(s["narration"]["text"] if isinstance(s.get("narration"), dict) else (s.get("narration") or "")
                                for s in tl.get("scenes", []))
                copied = artifacts.copied_phrases(said, _transcript(ws))
                if copied:
                    rep.error("timeline", "narration reuses inspiration wording: " + "; ".join(copied[:3]))
    return _print_report(rep, f"{what}: ok")


def cmd_adapt(args) -> int:
    ws = _ws(args)
    path = adapter.scaffold(ws, force=args.force)
    print(f"Wrote {path}. Complete every TODO from the brief, then `promo check creative`.")
    return 0


def cmd_compile(args) -> int:
    ws = _ws(args)
    rc, rep = timeline.compile_timeline(ws)
    code = _print_report(rep, "")
    if code:
        return code
    print(f"Compiled {len(rc['scenes'])} scenes · {rc['duration']:.1f}s · {len(rc['sound']['cues'])} sound cues · "
          f"{len(rc['narration']['lines'])} narration lines")
    print(f"Wrote {ws.render_config.name}, {ws.storyboard.name}, {ws.narration.name}")
    return 0


def cmd_voice(args) -> int:
    ws = _ws(args)
    cfg = ws.config()
    if args.provider:
        cfg["voice"]["provider"] = args.provider
    data = voiceover.render_voice(ws, read_json(ws.render_config), cfg)
    print(f"Voiceover: {len(data['lines'])} lines via {data['engine']}")
    return 0


def cmd_audio(args) -> int:
    ws = _ws(args)
    m = audio.build_master(ws, read_json(ws.render_config))
    kinds = {}
    for s in m["sources"]:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"Master: {ws.master_audio} · " + ", ".join(f"{v} {k}" for k, v in kinds.items()) + " · no music")
    return 0


def _aspects(args, ws: Workspace) -> list[str]:
    return args.aspect or ws.config()["format"]["aspects"]


def cmd_render(args) -> int:
    ws = _ws(args)
    for a in _aspects(args, ws):
        out = render.render(ws, a, quality=args.quality)
        print(f"  wrote {out}")
    return 0


def cmd_stills(args) -> int:
    ws = _ws(args)
    for a in _aspects(args, ws):
        for p in render.stills(ws, a, scenes=args.scene, at=args.at):
            print(f"  {p.relative_to(ws.root)}")
    return 0


def _find_videos(ws: Workspace, aspects: list[str], quality: str) -> dict[str, Path]:
    out = {}
    for a in aspects:
        p = ws.out_dir / f"promo-{a.replace(':', 'x')}{'-draft' if quality == 'draft' else ''}.mp4"
        out[a] = p
    return out


def cmd_qa(args) -> int:
    ws = _ws(args)
    quality = args.quality or ws.config()["render"]["quality"]
    rep = qa.run_qa(ws, _find_videos(ws, _aspects(args, ws), quality), scale=QUALITY[quality]["scale"])
    return _print_report(rep, f"QA passed. Report: {ws.qa_report}")


def cmd_build(args) -> int:
    """compile → voice → audio → render → qa, stopping at the first failure."""
    ws = _ws(args)
    for step in (cmd_compile, cmd_voice, cmd_audio, cmd_render, cmd_qa):
        print(f"\n── {step.__name__[4:]} ──")
        code = step(args)
        if code:
            return code
    return 0


def cmd_status(args) -> int:
    ws = _ws(args)
    if not ws.config_path.exists():
        print(f"No workspace at {ws.root}. Start with `promo init`.")
        return 1
    cfg = ws.config()
    insp = cfg["inspiration"].get("url")
    steps = [("config", ws.config_path), ("product scan", ws.scan), ("product brief", ws.brief)]
    if insp:
        steps += [("watch evidence", ws.evidence), ("inspiration prompt", ws.inspiration)]
    steps += [("creative prompt", ws.creative), ("timeline", ws.timeline), ("render config", ws.render_config),
              ("voiceover", ws.vo_dir / "manifest.json"), ("audio master", ws.master_audio),
              ("qa report", ws.qa_report)]
    print(f"Workspace {ws.root} · workflow: {'inspiration ' + insp if insp else 'master framework'}")
    for name, p in steps:
        print(f"  {'✓' if p.exists() else '·'} {name:<20} {p.relative_to(ws.root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="promo", description="Creative compiler for product promo films.")
    ap.add_argument("-w", "--workspace", default="promo", help="workspace folder (default ./promo)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check tools, renderer, watch skill, voice engines, disk")
    p = sub.add_parser("init", help="create the workspace")
    p.add_argument("--product", default=".", help="product repository root (default .)")
    p.add_argument("--name", help="product name as it should appear on screen")
    p.add_argument("--inspiration", help="YouTube URL, or 'none'")
    sub.add_parser("status", help="show which artifacts exist")
    sub.add_parser("scan", help="analyse the product repository → product-scan.json")
    p = sub.add_parser("capture", help="screenshot the running product into assets/captures/")
    p.add_argument("--url")
    p.add_argument("--routes", nargs="*", default=["/"])
    p.add_argument("--size", choices=sorted(capture.SIZES), default="desktop")
    p.add_argument("--launch", action="store_true", help="start the product with its dev command first")
    p.add_argument("--cmd", help="launch command override")
    p = sub.add_parser("watch", help="analyse the inspiration video with the watch skill")
    p.add_argument("url")
    p.add_argument("--detail", default="balanced", choices=["efficient", "balanced", "token-burner"])
    p = sub.add_parser("check", help="validate an artifact")
    p.add_argument("what", choices=["inspiration", "brief", "creative", "timeline", "all"])
    p = sub.add_parser("adapt", help="scaffold creative-prompt.md from the source + brief")
    p.add_argument("--force", action="store_true")
    sub.add_parser("compile", help="timeline.json → render-config.json, storyboard.md, narration.txt")
    p = sub.add_parser("voice", help="render the narration")
    p.add_argument("--provider", choices=sorted({"auto", "openrouter", "say", "files", "none"}))
    sub.add_parser("audio", help="mix effects + voice into the master (no music)")
    p = sub.add_parser("stills", help="render one frame per scene at any aspect, without a full render")
    p.add_argument("--aspect", action="append", choices=sorted(ASPECTS))
    p.add_argument("--scene", action="append", help="scene id (repeatable; default all)")
    p.add_argument("--at", type=float, default=0.85, help="position inside each scene, 0–1")
    for name in ("render", "qa", "build"):
        p = sub.add_parser(name, help={"render": "render the film", "qa": "verify the rendered film",
                                       "build": "compile → voice → audio → render → qa"}[name])
        p.add_argument("--aspect", action="append", choices=sorted(ASPECTS))
        p.add_argument("--quality", choices=["draft", "final"])
        if name == "build":
            p.add_argument("--provider", choices=sorted({"auto", "openrouter", "say", "files", "none"}))
    return ap


COMMANDS = {"doctor": cmd_doctor, "init": cmd_init, "status": cmd_status, "scan": cmd_scan,
            "capture": cmd_capture, "watch": cmd_watch, "check": cmd_check, "adapt": cmd_adapt,
            "compile": cmd_compile, "voice": cmd_voice, "audio": cmd_audio, "render": cmd_render,
            "qa": cmd_qa, "build": cmd_build, "stills": cmd_stills}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except PromoError as exc:
        print(exc.render(), file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
