"""Private, bounded original-footage preview for the HTML5/Three.js comparison.

Original uploaded recordings stay on disk. A browser-compatible visual
preview is transcoded only on demand; no public file endpoint is created.
Oversized videos require loading the user's own local file directly inside
the viewer rather than pretending an unrelated player is synchronized.
"""
from __future__ import annotations

import base64
from pathlib import Path
import shutil
import subprocess

MAX_INLINE_BYTES = 18 * 1024 * 1024


def source_video_path(job):
    if getattr(job, "source_kind", "file") != "file":
        return None
    source = getattr(job, "source", None)
    if not isinstance(source, (str, Path)):
        return None
    path = Path(source)
    return path if path.is_file() else None


def prepare_source_video(job, *, max_inline_bytes=MAX_INLINE_BYTES):
    """Return (private data URI or None, explanation).

    comparison_original.mp4 is a display proxy of the actual uploaded
    video, NOT the YOLO-annotated version. Timestamps are preserved.
    """
    original = source_video_path(job)
    if original is None:
        return None, "Original file isn't available on this server. Choose a local recording in the comparison viewer."
    output = Path(job.folder) / "comparison_original.mp4"
    if not output.is_file() or output.stat().st_size == 0:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return None, "FFmpeg unavailable. Choose an MP4 recording using the local video picker in the comparison viewer."
        try:
            result = subprocess.run([
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(original),
                "-map", "0:v:0", "-an",
                "-vf", "scale=w='min(960,iw)':h=-2:flags=bicubic",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "29",
                "-pix_fmt", "yuv420p", "-threads", "2",
                "-movflags", "+faststart",
                str(output),
            ], capture_output=True, text=True, timeout=150)
            if result.returncode or not output.is_file() or output.stat().st_size < 128:
                output.unlink(missing_ok=True)
                return None, "The original recording couldn't be encoded for this browser; select the file locally in the comparison panel."
        except (OSError, subprocess.TimeoutExpired):
            output.unlink(missing_ok=True)
            return None, "Encoding the original video timed out. Use the local file picker in the comparison panel."
    if output.stat().st_size > max_inline_bytes:
        return None, (
            "This original video is too large to embed securely in the 3D viewer. "
            "Select the original file using the viewer's local picker; it remains on your device."
        )
    return "data:video/mp4;base64," + base64.b64encode(output.read_bytes()).decode("ascii"), (
        "Browser-playable copy of the original footage; the video itself is not simulated or AI-annotated."
    )
