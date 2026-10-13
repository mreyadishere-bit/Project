"""Official traffic camera allowlist and health-check unit tests."""
import unittest
from unittest.mock import patch
import subprocess

from public_cameras import CAMERAS, get_camera, camera_choices
from camera_check import check_first_frame


class PublicCameraTests(unittest.TestCase):
    def test_curated_source_ids_resolve_and_no_untrusted_url(self):
        self.assertGreaterEqual(len(camera_choices()), 1)
        for key in camera_choices():
            info = get_camera(key)
            self.assertTrue(info["stream_url"].startswith("https://"))
            self.assertTrue(info["operator"])
        for untrusted in (
            "https://127.0.0.1:8080/live.m3u8",
            "http://metadata.google.internal/",
            "/etc/passwd",
            "youtube",
            ""
        ):
            with self.subTest(value=untrusted), self.assertRaises(ValueError):
                get_camera(untrusted)

    def test_health_check_rejects_unlisted_url_before_running_ffmpeg(self):
        with patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "curated"):
                check_first_frame("https://example.com/feed.m3u8")
            run.assert_not_called()

    def test_health_check_invalid_media_returns_error_not_false_positive(self):
        allowed = next(iter(CAMERAS.values()))["stream_url"]
        result = subprocess.CompletedProcess(args=[], returncode=1, stdout=b"", stderr=b"down")
        with patch("shutil.which", return_value="/usr/bin/ffmpeg"), patch(
            "subprocess.run", return_value=result
        ):
            with self.assertRaisesRegex(RuntimeError, "did not return"):
                check_first_frame(allowed)


if __name__ == "__main__":
    unittest.main()
