"""Regression checks for the local-only low-budget RTSP connection test."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from local_camera_probe import hikvision_rtsp, private_camera_ip, probe_capture


class Frame:
    shape = (720, 1280, 3)


class FakeCapture:
    def __init__(self, count=4):
        self.count = count
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return 25

    def read(self):
        if self.count <= 0:
            return False, None
        self.count -= 1
        return True, Frame()

    def release(self):
        self.released = True


class LocalCameraProbeTests(unittest.TestCase):
    def test_local_ip_only(self):
        self.assertEqual(private_camera_ip("192.168.1.64"), "192.168.1.64")
        self.assertEqual(private_camera_ip("10.0.0.2"), "10.0.0.2")
        with self.assertRaises(ValueError):
            private_camera_ip("8.8.8.8")
        with self.assertRaises(ValueError):
            private_camera_ip("127.0.0.1")
        with self.assertRaises(ValueError):
            private_camera_ip("localhost")

    def test_rtsp_url_escapes_credential_special_characters(self):
        url = hikvision_rtsp("192.168.0.8", "admin", "pa:ss@word", substream=True)
        self.assertEqual(url, "rtsp://admin:pa%3Ass%40word@192.168.0.8:554/Streaming/Channels/102")
        self.assertTrue(hikvision_rtsp("10.1.0.9", "u", "p").endswith("/101"))

    def test_bounded_video_probe_does_not_report_fake_metric_measurements(self):
        capture = FakeCapture(count=4)
        result = probe_capture(capture, seconds=10, max_frames=10)
        self.assertEqual(result["status"], "video_received")
        self.assertEqual(result["frames_received"], 4)
        self.assertEqual((result["width"], result["height"]), (1280, 720))
        self.assertEqual(result["reported_source_fps"], 25)
        self.assertNotIn("distance_m", result)
        self.assertNotIn("speed_kmh", result)

    def test_no_frames_reports_failure(self):
        with self.assertRaises(RuntimeError):
            probe_capture(FakeCapture(count=0), max_frames=2)


if __name__ == "__main__":
    unittest.main()
