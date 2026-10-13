"""Public YouTube live source validation and best-effort video URL resolution.

Only public, permitted, active YouTube videos with a canonical 11-character ID
are accepted. Never accept arbitrary network URLs, cookies or credentials.
"""
from __future__ import annotations
from urllib.parse import parse_qs, urlparse
import re

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}


def canonical_youtube_live_url(raw: str) -> str:
    if not raw or len(raw) > 2048:
        raise ValueError("Enter a valid public YouTube live URL.")
    parsed = urlparse(raw.strip())
    if (parsed.scheme != "https" or parsed.netloc.lower() not in HOSTS
            or parsed.username or parsed.password or parsed.port is not None):
        raise ValueError("Only HTTPS youtube.com / youtu.be URLs are accepted.")
    host = parsed.netloc.lower()
    parts = parsed.path.strip("/").split("/")
    if host.endswith("youtu.be"):
        video_id = parts[0] if len(parts) == 1 else ""
    elif parsed.path == "/watch":
        videos = parse_qs(parsed.query).get("v", [])
        video_id = videos[0] if len(videos) == 1 else ""
    elif len(parts) == 2 and parts[0] == "live":
        video_id = parts[1]
    else:
        video_id = ""
    if not VIDEO_ID.fullmatch(video_id):
        raise ValueError("Use a specific YouTube video/live link such as https://www.youtube.com/live/VIDEO_ID.")
    return f"https://www.youtube.com/watch?v={video_id}"


def resolve_youtube_live(raw_url: str) -> tuple[str, str]:
    """Resolve a public live video. Requires yt-dlp and network access.

    Returns (temporary direct media URL, public title). URL may expire and
    can fail on cloud providers because of restrictions or geo-blocking.
    """
    url = canonical_youtube_live_url(raw_url)
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("The yt-dlp package is missing; install requirements.txt.") from exc

    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "skip_download": True, "socket_timeout": 15,
        "retries": 1, "extractor_retries": 1,
        "format": "best[height<=720]/best",
        "ignoreerrors": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise RuntimeError(
            "Could not access this public YouTube broadcast. It may be offline, "
            "private, geo-restricted, or blocked on this server. "
            f"Extractor said: {str(exc)[:250]}"
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError("YouTube did not provide playable metadata.")
    if info.get("is_live") is not True and info.get("live_status") != "is_live":
        raise ValueError("This YouTube video is not currently live. Use video upload for recordings.")
    stream_url = info.get("url")
    if not isinstance(stream_url, str) or not stream_url.startswith("https://"):
        # Never forward arbitrary content, and never expose the media URL to the UI.
        raise RuntimeError("No supported HTTPS video stream was returned for this live broadcast.")
    title = str(info.get("title") or "YouTube live road camera")[:120]
    return stream_url, title
