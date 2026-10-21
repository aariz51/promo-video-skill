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

from . import adapter, analyzer, artifacts, audio, capture, deliver, direction, discovery, providers, qa, \
    questions, reference_input, render, screenshots, timeline, voiceover, watcher
from .config import AUDIO_MODES, ASPECTS, PROVIDER_KEYS, Workspace, audio_mode, init_workspace, mode, \
    reference_source
from .util import RENDERER_DIR, PromoError, Report, free_gb, read_json, write_json


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
    for prov, var in PROVIDER_KEYS.items():
        # Only whether the variable is set; the value is never printed.
        rows.append((f"voice: {prov}", bool(os.environ.get(var)), f"{var} {'set' if os.environ.get(var) else 'not set'}"))
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


def _runtime(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    parts = [int(float(x)) for x in text.replace("–", "-").split("-") if x.strip()]
    if len(parts) == 1:
        parts = [max(10, parts[0] - 5), parts[0] + 5]
    if len(parts) != 2:
        raise PromoError(f"runtime must be seconds or a range like 30-45, not {text!r}")
    return parts[0], parts[1]


def cmd_init(args) -> int:
    ws = _ws(args)
    raw = args.reference if args.reference is not None else args.inspiration
    ref = reference_input.resolve(raw, base=Path.cwd()).as_config() if raw is not None else None
    if args.provider and args.provider not in ("auto",):
        providers.require(args.provider)
    path = init_workspace(ws, product_root=Path(args.product), name=args.name, reference=ref,
                          audio=args.audio, provider=None if args.provider in (None, "auto") else args.provider,
                          aspects=args.formats, runtime=_runtime(args.runtime))
    cfg = ws.config()
    print(f"Workspace ready: {ws.root}\nConfig: {path}")
    src = reference_source(cfg)
    print("Mode:", f"reference-driven ({cfg['reference']['kind']}: {src})" if src else
          "autonomous (master creative framework)" if "reference" in cfg["decided"] else "not decided yet")
    print("Audio:", audio_mode(cfg) + (" (music: never)" if "audio" in cfg["decided"] else " (default; not decided yet)"))
    open_q = questions.plan(ws)
    if open_q:
        print(f"Open questions: {', '.join(q['id'] for q in open_q)} (see `promo questions`)")
    return 0


def cmd_questions(args) -> int:
    ws = _ws(args)
    qs = questions.plan(ws)
    if args.json:
        print(json.dumps(qs, indent=2))
    elif not qs:
        print("Nothing to ask: every opening decision is known.")
    else:
        for q in qs:
            print(f"- [{q['id']}] {q['question']}\n    record with: {q['answer']}")
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


def cmd_discover(args) -> int:
    ws = _ws(args)
    res = discovery.run(ws, launch=not args.no_launch, url=args.url, routes=args.routes, inspect_mobile=not args.no_mobile,
                        size=args.size, supplied=[Path(x) for x in args.supplied or []])
    m, th = res["manifest"], res["theme"]
    print(f"{discovery.STAGE}: {m['product']}")
    for label, rep in (("web", m["web"]), ("mobile", m["mobile"])):
        print(f"  {label:<7} {rep['status']}" + (f" (blocked at {rep['stage']})" if rep.get("stage") else ""))
        for lim in rep.get("limitations", [])[:6]:
            print(f"          · {lim}")
    sel = [x for x in m["screenshots"] if x["selected"]]
    print(f"  screens {len(m['screenshots'])} candidates, {len(sel)} selected: " + (", ".join(x["id"] for x in sel) or
          "none — no genuine screenshot is available"))
    pr = th["promo"]
    print(f"  theme   {th['original']['defaultMode']} · ground {pr['ground']} · ink {pr['ink']} · accent {pr['accent']} · "
          f"type {pr['fontHead']} · {', '.join(c['label'] for c in th['original']['classification'])}")
    print(f"Wrote {ws.product_analysis.name}, {ws.theme_analysis.name}, {ws.theme.name}, {ws.asset_inventory.name}, "
          f"{ws.screenshot_manifest.name}. Look at every selected screenshot before the storyboard.")
    return 0


def cmd_select(args) -> int:
    ws = _ws(args)
    m = screenshots.load(ws.screenshot_manifest)
    if m.get("stage") != discovery.STAGE:
        raise PromoError("no screenshot manifest yet", hint="run `promo discover`")
    known = screenshots.by_id(m)
    for sid, verdict in [(x, "approved") for x in args.approve or []] + [(x, "rejected") for x in args.reject or []]:
        if sid not in known:
            raise PromoError(f"no screenshot '{sid}' in the manifest")
        if verdict == "approved" and known[sid]["source"] == "illustration":
            raise PromoError(f"'{sid}' is an illustration; it can only be used in a scene marked illustrative")
        known[sid]["override"], known[sid]["overrideReason"] = verdict, args.reason
    screenshots.select(m, ws.root, max_selected=args.max)
    screenshots.save(ws.screenshot_manifest, m)
    for x in sorted(m["screenshots"], key=lambda x: (not x["selected"], x["id"])):
        print(f"  {'✓' if x['selected'] else '·'} {x['id']:<28} {x['source']:<12} {x['reason']}")
    return 0


def cmd_watch(args) -> int:
    ws = _ws(args)
    source = args.url or reference_source(ws.config())
    if not source:
        raise PromoError("no reference video is configured", hint="`promo init --reference <url|path>` first")
    ev = watcher.watch(ws, source, detail=args.detail, refresh=args.refresh, no_whisper=args.no_whisper)
    print(watcher.evidence_summary(ev))
    print(f"\nBreakdown: {ws.reference_dir / 'breakdown.json'} · contact sheets: {ws.reference_dir / 'sheets'}")
    print("Next: `promo direction` scaffolds CREATIVE_DIRECTION.md from the measurements. "
          "Read every contact sheet and evidence frame before filling it in.")
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
    uses_insp = mode(cfg) == "reference"
    if what == "direction" or (what == "all" and uses_insp and not ws.inspiration.exists()):
        if not ws.direction.exists():
            rep.error(ws.direction.name, "missing (run `promo direction`)")
        else:
            rep.extend(direction.check(ws.direction.read_text(), direction.load_breakdown(ws), ws.root, _transcript(ws)))
    if what == "inspiration" or (what == "all" and uses_insp and ws.inspiration.exists()):
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
            rules = (direction.parse_rules(ws.direction.read_text()) if uses_insp and ws.direction.exists() else
                     artifacts.parse_rules(ws.inspiration.read_text()) if uses_insp and ws.inspiration.exists() else [])
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


def cmd_direction(args) -> int:
    ws = _ws(args)
    if mode(ws.config()) != "reference":
        raise PromoError("CREATIVE_DIRECTION.md is scaffolded from a reference; this run is autonomous",
                         hint="in autonomous mode `promo compile` writes it from creative-prompt.md")
    path = direction.scaffold(ws, force=args.force)
    print(f"Wrote {path}. Read every frame and contact sheet in reference/, replace every TODO, "
          "then `promo check direction`.")
    return 0


def cmd_storyboard(args) -> int:
    ws = _ws(args)
    if mode(ws.config()) != "reference":
        raise PromoError("`promo storyboard` derives the timeline from a reference; this run is autonomous",
                         hint="write timeline.json from creative-prompt.md (docs/timeline.md)")
    path = direction.storyboard(ws, force=args.force)
    tl = read_json(path)
    print(f"Wrote {path}: {len(tl['scenes'])} scenes · {sum(s['duration'] for s in tl['scenes']):.1f}s · "
          f"transitions {', '.join(s.get('transition', {}).get('type', '—') for s in tl['scenes'][1:])}")
    print("Fill kind, purpose, props (and narration) for each scene from the brief; keep ref, duration and "
          "transition, or add a `deviation` saying why. Then `promo check timeline`.")
    return 0


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
    rep = qa.run_qa(ws, _find_videos(ws, _aspects(args, ws), quality), quality)
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


def cmd_deliver(args) -> int:
    ws = _ws(args)
    m = deliver.deliver(ws, out=Path(args.out) if args.out else None, include_drafts=args.drafts, force=args.force)
    dest = Path(args.out).resolve() if args.out else ws.root / "deliver"
    print(f"Delivered to {dest}: {sum(1 for f in m['files'] if f['path'].startswith('videos/'))} film(s), "
          f"QA {m['qa']}, editable project in remotion/")
    return 0


def cmd_status(args) -> int:
    ws = _ws(args)
    if not ws.config_path.exists():
        print(f"No workspace at {ws.root}. Start with `promo init`.")
        return 1
    cfg = ws.config()
    insp = reference_source(cfg)
    steps = [("config", ws.config_path), ("product scan", ws.scan), ("product analysis", ws.product_analysis),
             ("theme", ws.theme), ("screenshot manifest", ws.screenshot_manifest), ("product brief", ws.brief)]
    if insp:
        steps += [("watch evidence", ws.evidence), ("inspiration prompt", ws.inspiration)]
    steps += [("creative prompt", ws.creative), ("timeline", ws.timeline), ("render config", ws.render_config),
              ("voiceover", ws.vo_dir / "manifest.json"), ("audio master", ws.master_audio),
              ("qa report", ws.qa_report)]
    print(f"Workspace {ws.root} · mode: {'reference ' + insp if insp else 'autonomous'} · audio: {audio_mode(cfg)}")
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
    p.add_argument("--reference", help="reference video: URL, local file path, or 'none' (decides the mode)")
    p.add_argument("--inspiration", help=argparse.SUPPRESS)  # v4 name for --reference
    p.add_argument("--audio", choices=list(AUDIO_MODES), help="voiceover (+effects) | effects | silent; never music")
    p.add_argument("--provider", choices=sorted({"auto", "openrouter", "openai", "say", "files"}))
    p.add_argument("--formats", nargs="+", choices=list(ASPECTS))
    p.add_argument("--runtime", help="seconds, or a range like 30-45")
    p = sub.add_parser("questions", help="the opening questions still open (never re-asks a decided one)")
    p.add_argument("--json", action="store_true")
    sub.add_parser("status", help="show which artifacts exist")
    sub.add_parser("scan", help="analyse the product repository → product-scan.json")
    p = sub.add_parser("capture", help="screenshot the running product into assets/captures/")
    p.add_argument("--url")
    p.add_argument("--routes", nargs="*", default=["/"])
    p.add_argument("--size", choices=sorted(capture.SIZES), default="desktop")
    p.add_argument("--launch", action="store_true", help="start the product with its dev command first")
    p.add_argument("--cmd", help="launch command override")
    p = sub.add_parser("discover", help="PRODUCT_THEME_DISCOVERY: codebase, theme, live app, real screenshots")
    p.add_argument("--no-launch", action="store_true", help="do not start the app (codebase only; recorded as such)")
    p.add_argument("--url", help="an already-running, authorised instance of the product (test environment)")
    p.add_argument("--routes", nargs="*", help="routes to inspect (default: the scan's static routes, prioritised)")
    p.add_argument("--no-mobile", action="store_true", help="skip simulator/emulator inspection")
    p.add_argument("--size", choices=sorted(capture.SIZES), default="desktop")
    p.add_argument("--supplied", nargs="*", help="genuine screenshots you already have")
    p = sub.add_parser("select", help="review or override the screenshot selection")
    p.add_argument("--approve", nargs="*")
    p.add_argument("--reject", nargs="*")
    p.add_argument("--reason", help="why (recorded in the manifest)")
    p.add_argument("--max", type=int, default=screenshots.MAX_SELECTED)
    p = sub.add_parser("watch", help="analyse the reference video with the watch skill")
    p.add_argument("url", nargs="?", help="default: the configured reference")
    p.add_argument("--detail", default="balanced", choices=["efficient", "balanced", "token-burner"])
    p.add_argument("--refresh", action="store_true", help="download and measure again instead of reusing")
    p.add_argument("--no-whisper", action="store_true",
                   help="never send the reference's audio to a transcription API (captions only)")
    p = sub.add_parser("check", help="validate an artifact")
    p.add_argument("what", choices=["direction", "inspiration", "brief", "creative", "timeline", "all"])
    p = sub.add_parser("direction", help="Mode B: scaffold CREATIVE_DIRECTION.md from the measured reference")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("storyboard", help="Mode B: timeline.json skeleton with the reference's structure")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("adapt", help="scaffold creative-prompt.md from the source + brief")
    p.add_argument("--force", action="store_true")
    sub.add_parser("compile", help="timeline.json → render-config.json, storyboard.md, narration.txt")
    p = sub.add_parser("voice", help="render the narration")
    p.add_argument("--provider", choices=sorted({"auto", "openrouter", "openai", "say", "files", "none"}))
    sub.add_parser("audio", help="mix effects + voice into the master (no music)")
    p = sub.add_parser("stills", help="render one frame per scene at any aspect, without a full render")
    p.add_argument("--aspect", action="append", choices=sorted(ASPECTS))
    p.add_argument("--scene", action="append", help="scene id (repeatable; default all)")
    p.add_argument("--at", type=float, default=0.85, help="position inside each scene, 0–1")
    p = sub.add_parser("deliver", help="assemble films, direction, reports and an editable Remotion project")
    p.add_argument("--out", help="destination (default promo/deliver)")
    p.add_argument("--drafts", action="store_true", help="include draft renders")
    p.add_argument("--force", action="store_true", help="deliver even though QA did not pass")
    for name in ("render", "qa", "build"):
        p = sub.add_parser(name, help={"render": "render the film", "qa": "verify the rendered film",
                                       "build": "compile → voice → audio → render → qa"}[name])
        p.add_argument("--aspect", action="append", choices=sorted(ASPECTS))
        p.add_argument("--quality", choices=["draft", "final"])
        if name == "build":
            p.add_argument("--provider", choices=sorted({"auto", "openrouter", "openai", "say", "files", "none"}))
    return ap


COMMANDS = {"doctor": cmd_doctor, "init": cmd_init, "questions": cmd_questions, "status": cmd_status, "scan": cmd_scan,
            "capture": cmd_capture, "discover": cmd_discover, "select": cmd_select, "watch": cmd_watch, "check": cmd_check, "adapt": cmd_adapt,
            "direction": cmd_direction, "storyboard": cmd_storyboard, "deliver": cmd_deliver,
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
