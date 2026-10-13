"""Bounded live-video frame decoder using FFmpeg's rawvideo pipe.

This module does not extract, decrypt or bypass YouTube content. It takes an
already-authorized media URL obtained from the public source resolver.
No shell is involved, and temporary media URLs are never written to logs.
"""
from __future__ import annotations

import shutil
import subprocess
import threading
from urllib.parse import urlsplit

import numpy as np

WIDTH = 640
HEIGHT = 360
FRAME_BYTES = WIDTH * HEIGHT * 3


class FFmpegLiveCapture:
    """An OpenCV-like reader of the latest available decoded video frames.

    A fixed output resolution keeps memory and read sizes bounded.
    Release stops the FFmpeg subprocess, including blocked network reads.
    """

    def __init__(self, url: str, *, allow_local_for_tests: bool = False,
                 width: int = WIDTH, height: int = HEIGHT, fps: int = 5):
        if not isinstance(url, str) or len(url) > 8192:
            raise ValueError("Invalid live media URL.")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password):
            if not (allow_local_for_tests and parsed.scheme == "file"):
                raise ValueError("Only resolved HTTPS live media links are supported.")
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("FFmpeg is missing on the server. Install ffmpeg in packages.txt.")
        if not 1 <= fps <= 15 or width <= 0 or height <= 0 or width > 1280 or height > 720:
            raise ValueError("Invalid live decoding configuration.")
        self.width = width
        self.height = height
        self.frame_bytes = width * height * 3
        self.fps = fps
        self._closed = threading.Event()
        # Fixed-size video with aspect-preserving letterbox. No dynamic allocation
        # proportional to the source stream's potentially untrusted resolution.
        vf = (f"fps={fps},scale={width}:{height}:force_original_aspect_ratio=decrease,"
              f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
        args = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
        if parsed.scheme == "https":
            args.extend([
                "-rw_timeout", "12000000",
                "-user_agent", "Mozilla/5.0 (compatible; SmartRoadResearch/1.0)",
                "-referer", "https://www.youtube.com/",
            ])
        args.extend([
            "-i", url, "-map", "0:v:0", "-an", "-sn", "-dn",
            "-vf", vf, "-pix_fmt", "bgr24", "-f", "rawvideo", "pipe:1",
        ])
        self._process = subprocess.Popen(
            args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0,
        )

    def isOpened(self):
        return not self._closed.is_set() and self._process.poll() is None

    def set(self, *_):
        return False

    def get(self, *_):
        return float(self.fps)

    def read(self):
        if self._closed.is_set() or self._process.stdout is None:
            return False, None
        chunks = bytearray()
        while len(chunks) < self.frame_bytes and not self._closed.is_set():
            try:
                data = self._process.stdout.read(self.frame_bytes - len(chunks))
            except (OSError, ValueError):
                return False, None
            if not data:
                return False, None
            chunks.extend(data)
        if len(chunks) != self.frame_bytes:
            return False, None
        frame = np.frombuffer(chunks, dtype=np.uint8).reshape(
            (self.height, self.width, 3)).copy()
        return True, frame

    def release(self):
        if self._closed.is_set():
            return
        self._closed.set()
        p = self._process
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)
        if p.stdout:
            p.stdout.close()
