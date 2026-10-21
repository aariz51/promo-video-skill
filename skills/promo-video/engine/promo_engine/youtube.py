"""YouTube URL validation. Rejects anything we cannot confidently resolve to one video."""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from .util import PromoError

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
          "youtube-nocookie.com", "www.youtube-nocookie.com"}
_PATH_KINDS = ("shorts", "embed", "live", "v")


@dataclass(frozen=True)
class YouTubeVideo:
    id: str

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.id}"


def parse_youtube_url(raw: str) -> YouTubeVideo:
    """Return the canonical video, or raise PromoError explaining what is wrong."""
    text = (raw or "").strip().strip("<>").strip()
    if not text:
        raise PromoError("no inspiration URL given")
    if "://" not in text:
        text = "https://" + text
    u = urlparse(text)
    if u.scheme not in ("http", "https"):
        raise PromoError(f"not a web URL: {raw!r}")
    host = (u.hostname or "").lower()
    vid: str | None = None
    if host in ("youtu.be", "www.youtu.be"):
        vid = u.path.lstrip("/").split("/")[0]
    elif host in _HOSTS:
        parts = [p for p in u.path.split("/") if p]
        if parts[:1] == ["watch"]:
            vid = (parse_qs(u.query).get("v") or [None])[0]
        elif len(parts) >= 2 and parts[0] in _PATH_KINDS:
            vid = parts[1]
        elif parts[:1] == ["playlist"] or "list" in parse_qs(u.query) and not parse_qs(u.query).get("v"):
            raise PromoError("that is a playlist, not a single video",
                             hint="open the video you want and copy its own URL")
        elif parts and (parts[0].startswith("@") or parts[0] in ("channel", "c", "user")):
            raise PromoError("that is a channel page, not a video",
                             hint="open the video you want and copy its own URL")
    else:
        raise PromoError(f"not a YouTube URL: {raw!r}",
                         hint="paste a youtube.com/watch?v=…, youtu.be/…, or youtube.com/shorts/… link")
    if not vid or not _ID.match(vid):
        raise PromoError(f"could not find a valid video id in {raw!r}",
                         hint="YouTube video ids are 11 characters, e.g. youtu.be/dQw4w9WgXcQ")
    return YouTubeVideo(vid)
