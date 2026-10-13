"""Real, offline FFmpeg HLS decoder integration test: no YouTube or secrets."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np

from live_decoder import FFmpegLiveCapture


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg binary not installed on CI")
class LiveDecoderTests(unittest.TestCase):
    def test_hls_frame_decoding_and_resource_cleanup(self):
        """Generate a tiny legal synthetic HLS playlist, then decode actual frames."""
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "test-road.m3u8"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=320x180:rate=5",
                "-t", "3", "-c:v", "mpeg2video",
                "-f", "hls", "-hls_time", "1",
                "-hls_list_size", "0", "-y", str(playlist),
            ], check=True, timeout=25, capture_output=True)

            cap = FFmpegLiveCapture(
                playlist.as_uri(), allow_local_for_tests=True,
                width=320, height=180, fps=5
            )
            try:
                self.assertTrue(cap.isOpened())
                ok, frame = cap.read()
                self.assertTrue(ok, "FFmpeg did not supply a decoded HLS frame")
                self.assertEqual(frame.shape, (180, 320, 3))
                self.assertGreater(float(frame.std()), 1)
            finally:
                cap.release()
            self.assertFalse(cap.isOpened())
            cap.release()  # idempotent

    def test_refuses_local_urls_in_production(self):
        with self.assertRaisesRegex(ValueError, "Only resolved HTTPS"):
            FFmpegLiveCapture("file:///tmp/nonpublic.mp4")

    def test_refuses_arbitrary_file_or_http_sources(self):
        for url in (
            "http://127.0.0.1/live.m3u8",
            "file:///etc/passwd",
            "https://user:pass@example.com/live.m3u8"
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                FFmpegLiveCapture(url)


if __name__ == "__main__":
    unittest.main()
