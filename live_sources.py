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



def choose_frame_stream(info: dict) -> str:
    """Select an HTTPS video stream that OpenCV/FFmpeg can plausibly decode.

    Prefer HLS playlists, then direct nonfragmented video. This is only
    a transport selection, NOT a way to bypass access restrictions.
    """
    formats = info.get("formats") or []
    candidates = []
    for entry in formats:
        address = entry.get("url")
        if (not isinstance(address, str) or not address.startswith("https://")
                or entry.get("vcodec") in (None, "none")
                or entry.get("has_drm") or entry.get("drm_families")):
            continue
        protocol = entry.get("protocol") or ""
        if protocol in ("m3u8", "m3u8_native"):
            priority = 0
        elif protocol in ("https", "http") and not entry.get("fragments"):
            priority = 1
        else:
            # DASH fragment playlists and audio-only media are not playable
            # through a simple cv2.VideoCapture(url) call.
            continue
        height = entry.get("height")
        try:
            height = int(height or 0)
        except (TypeError, ValueError):
            height = 0
        # Favor lower decode costs around 480p, rather than massive live video.
        candidates.append((priority, abs(height - 480) if height else 10_000, address))
    if candidates:
        return min(candidates)[2]
    direct = info.get("url")
    if isinstance(direct, str) and direct.startswith("https://") and not info.get("requested_formats"):
        return direct
    raise RuntimeError(
        "YouTube did not provide a usable video stream for this server "
        "(no compatible HLS or direct HTTPS video formats). "
        "This is a source-access limitation, not an AI detection failure. "
        "Try a public camera feed that provides an authorized HLS/RTSP stream "
        "or upload permitted footage."
    )


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
        "ignore_no_formats_error": True,
        "ignoreerrors": False,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        error_text = str(exc).lower()
        if ("not a bot" in error_text or "sign in to confirm" in error_text
                or "login required" in error_text):
            raise RuntimeError(
                "YouTube blocked automated video access from this server. "
                "The original video might still play normally on YouTube, but the AI "
                "cannot analyze its frames through this connection. "
                "Use an operator-authorized machine-readable feed or upload permitted footage."
            ) from exc
        raise RuntimeError(
            "Unable to access this broadcast from the analysis server. "
            "It may be offline, private, geographically restricted, or temporarily inaccessible. "
            "Try another authorized public live source or an uploaded video."
        ) from exc
    if not isinstance(info, dict):
        raise RuntimeError("YouTube did not provide usable video metadata.")
    known_status = info.get("live_status")
    if known_status in {"not_live", "was_live", "post_live", "is_upcoming"}:
        raise ValueError("This YouTube video is not currently live. Use video upload for recordings.")
    # Check usable media before claiming a live status; metadata can be empty
    # on a restricted server, so is_live may be unknown even for live feeds.
    stream_url = choose_frame_stream(info)
    if info.get("is_live") is not True and known_status != "is_live":
        raise ValueError("Cannot confirm this is an active live broadcast from this server.")
    title = str(info.get("title") or "YouTube live road camera")[:120]
    return stream_url, title
