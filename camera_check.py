"""Read exactly one frame from a reviewed public camera using FFmpeg.

Health test is opt-in, single-frame, bounded to 18s and no persisted footage.
"""
from __future__ import annotations
import shutil
import subprocess

import cv2
import numpy as np

from public_cameras import CAMERAS


def check_first_frame(stream_url: str):
    allowed = {v["stream_url"] for v in CAMERAS.values()}
    if stream_url not in allowed:
        raise ValueError("Only curated official road camera URLs may be tested.")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is missing from the app server.")
    args = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-rw_timeout", "7000000", "-i", stream_url, "-an",
        "-sn", "-dn", "-frames:v", "1", "-vf",
        "scale=640:-2:force_original_aspect_ratio=decrease",
        "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]
    try:
        completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=18)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("No decodable camera frame was received within 18 seconds.") from exc
    if completed.returncode != 0 or len(completed.stdout) < 1000:
        raise RuntimeError(
            "The agency camera did not return an FFmpeg-decodable frame. "
            "Try another camera or try again later."
        )
    data = np.frombuffer(completed.stdout, dtype=np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        raise RuntimeError("Received bytes from the source, but could not decode a valid camera image.")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
