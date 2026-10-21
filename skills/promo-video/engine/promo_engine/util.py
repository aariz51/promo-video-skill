"""Shared helpers: errors, subprocess, paths, JSON and time formatting."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

SKILL_DIR = Path(__file__).resolve().parents[2]
RENDERER_DIR = SKILL_DIR / "renderer"
FRAMEWORK_DIR = SKILL_DIR / "framework"
FONTS_DIR = RENDERER_DIR / "public" / "fonts"


SECRET_VARS = ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "OPENROUTER_KEY", "OPENAI_KEY", "GROQ_API_KEY")


def redact(text: str) -> str:
    """Replace any configured API key value that appears in `text` (defence in depth:
    keys are never put into commands, files or messages in the first place)."""
    for var in SECRET_VARS:
        v = (os.environ.get(var) or "").strip()
        if len(v) >= 8:
            text = text.replace(v, f"<{var}>")
    return text


_SECRETISH = re.compile(r"((?:[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASS|PWD|DSN|URL))\s*[=:]\s*)\S+", re.I)
_CRED_URL = re.compile(r"(\b[a-z][\w+.-]*://)[^\s:/@]+:[^\s@/]+@", re.I)


def scrub(text: str) -> str:
    """Anything written for people to read (reports, launch logs): drop credential-shaped values."""
    text = redact(text)
    text = _CRED_URL.sub(r"\1<credentials>@", text)
    return _SECRETISH.sub(r"\1<redacted>", text)


class PromoError(Exception):
    """A failure the user can act on. `hint` says what to do next."""

    def __init__(self, message: str, hint: str | None = None, code: int = 1):
        super().__init__(message)
        self.hint = hint
        self.code = code

    def render(self) -> str:
        return redact(f"error: {self}" + (f"\n  → {self.hint}" if self.hint else ""))


@dataclass
class Issue:
    """One validation finding. `error` blocks the pipeline; `warning` is reported."""

    level: str  # "error" | "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    def error(self, where: str, message: str) -> None:
        self.issues.append(Issue("error", where, message))

    def warn(self, where: str, message: str) -> None:
        self.issues.append(Issue("warning", where, message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "Report") -> None:
        self.issues.extend(other.issues)

    def summary(self) -> str:
        if not self.issues:
            return "ok"
        return "\n".join(str(i) for i in self.issues)


def require_tools(*names: str) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        raise PromoError(
            "missing required tool(s) on PATH: " + ", ".join(missing),
            hint="macOS: brew install ffmpeg yt-dlp node · Debian: sudo apt install ffmpeg nodejs",
        )


def run(cmd: Sequence[str], *, cwd: str | Path | None = None, input: bytes | None = None,
        env: dict | None = None, check: bool = True, text: bool = True) -> subprocess.CompletedProcess:
    """Run a command, capturing output. On failure, raise with the stderr tail."""
    res = subprocess.run(list(cmd), cwd=cwd, input=input, env=env, capture_output=True,
                         text=text if input is None else False)
    if check and res.returncode != 0:
        err = res.stderr if isinstance(res.stderr, str) else res.stderr.decode(errors="replace")
        tail = "\n  ".join(err.strip().splitlines()[-8:])
        raise PromoError(f"{Path(cmd[0]).name} failed (exit {res.returncode}):\n  {tail}")
    return res


def read_json(path: str | Path) -> Any:
    p = Path(path)
    if not p.exists():
        raise PromoError(f"missing file: {p}")
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise PromoError(f"{p} is not valid JSON: {exc}") from exc


def write_json(path: str | Path, data: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return p


def fmt_time(seconds: float) -> str:
    """m:ss.s for artifacts and reports."""
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def parse_time(value: str) -> float:
    """Parse SS, M:SS or H:MM:SS (fractions allowed) into seconds."""
    parts = [float(p) for p in value.strip().split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def free_gb(path: str | Path) -> float:
    p = Path(path)
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


def ffprobe_json(path: str | Path) -> dict:
    res = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    return json.loads(res.stdout)


def media_duration(path: str | Path) -> float:
    return float(ffprobe_json(path)["format"]["duration"])
