"""Mode selection: what the user supplied as a reference decides the mode. Never asked.

  nothing / "none" / "no"          → Mode A, autonomous (master creative framework)
  YouTube URL                      → Mode B, reference-driven (validated to one video)
  other http(s) URL                → Mode B (yt-dlp decides at `promo watch` whether it is a video)
  existing local video file        → Mode B (must contain a decodable video stream)

Anything else is an error with a reason. A path that does not exist is never re-read as a
URL, and a URL is never guessed from text.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .util import PromoError
from .youtube import parse_youtube_url

NO_REFERENCE = {"", "none", "no", "n", "nope", "skip", "n/a", "na", "false"}
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
YOUTUBE_HOSTS = ("youtube.com", "youtu.be", "youtube-nocookie.com")

AUTONOMOUS = "autonomous"
REFERENCE = "reference"


@dataclass(frozen=True)
class Reference:
    kind: str  # "none" | "youtube" | "url" | "file"
    source: str | None  # canonical URL or absolute path

    @property
    def mode(self) -> str:
        return AUTONOMOUS if self.kind == "none" else REFERENCE

    def as_config(self) -> dict:
        return {"kind": self.kind, "source": self.source}


def _looks_like_path(text: str) -> bool:
    return (text.startswith(("/", "~", "./", "../")) or Path(text).suffix.lower() in VIDEO_EXT
            or ("/" in text and "://" not in text and not text.split("/")[0].count(".")))


def _probe_video(path: Path) -> None:
    if shutil.which("ffprobe") is None:
        raise PromoError("ffprobe is needed to check a local reference video", hint="brew install ffmpeg")
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration",
                          "-of", "json", str(path)], capture_output=True, text=True)
    if res.returncode != 0:
        raise PromoError(f"the reference file cannot be decoded: {path}",
                         hint="re-export it as H.264 MP4, or supply a different reference")
    info = json.loads(res.stdout or "{}")
    if not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
        raise PromoError(f"the reference file has no video stream: {path}")
    if float((info.get("format") or {}).get("duration") or 0) <= 0:
        raise PromoError(f"the reference file has no measurable duration (truncated?): {path}")


def resolve(raw: str | None, *, base: Path | None = None) -> Reference:
    """Turn the user's answer to "do you have a reference video?" into a Reference."""
    text = (raw or "").strip().strip("<>\"'").strip()
    if text.lower() in NO_REFERENCE:
        return Reference("none", None)
    if "://" not in text and _looks_like_path(text):
        p = Path(text).expanduser()
        if not p.is_absolute() and base is not None:
            p = base / p
        if not p.exists():
            raise PromoError(f"reference file not found: {p}", hint="check the path, or answer 'no' for the autonomous film")
        if not p.is_file():
            raise PromoError(f"reference path is not a file: {p}")
        if p.suffix.lower() not in VIDEO_EXT:
            raise PromoError(f"unsupported reference file type '{p.suffix}'",
                             hint=f"use one of {', '.join(sorted(VIDEO_EXT))}")
        _probe_video(p)
        return Reference("file", str(p.resolve()))
    candidate = text if "://" in text else "https://" + text
    u = urlparse(candidate)
    host = (u.hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in YOUTUBE_HOSTS):
        return Reference("youtube", parse_youtube_url(text).url)
    if u.scheme not in ("http", "https"):
        raise PromoError(f"not a web URL or a local video file: {raw!r}")
    if not host or "." not in host:
        raise PromoError(f"not a usable URL or local video file: {raw!r}",
                         hint="paste a full video URL (https://…) or a path to a video file, or answer 'no'")
    return Reference("url", u.geturl())
