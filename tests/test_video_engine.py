"""Unit/integration tests: engine can finish a clip without a one-minute cap."""
import csv
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from video_engine import VideoJob, VideoSettings, motion_direction, frame_counts


class FakeTensor:
    def __init__(self, value):
        self.value = value
    def int(self):
        return self
    def cpu(self):
        return self
    def tolist(self):
        return self.value


class FakeBoxes:
    def __init__(self):
        self.xyxy = FakeTensor([[20, 10, 75, 60]])
        self.conf = FakeTensor([0.8])
        self.cls = FakeTensor([2])
        self.id = FakeTensor([7])
    def __len__(self):
        return 1


class FakeResult:
    names = {2: "car"}
    boxes = FakeBoxes()
    def __init__(self, frame):
        self.frame = frame
    def plot(self):
        return self.frame


fake_torch = types.ModuleType("torch")
fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)

class FakeYOLO:
    names = {0: "person", 2: "car", 9: "traffic light"}
    def __init__(self, name):
        pass
    def track(self, frame, **kwargs):
        return [FakeResult(frame)]


def create_video(path, frames=24, fps=12):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (128, 96))
    assert writer.isOpened(), "OpenCV test video writer unavailable"
    for _ in range(frames):
        writer.write(np.zeros((96, 128, 3), dtype=np.uint8))
    writer.release()


class VideoTests(unittest.TestCase):
    def test_direction_is_pixels_not_speed(self):
        self.assertEqual(motion_direction(None, (10, 10)), "new")
        self.assertEqual(motion_direction((10, 10), (26, 10)), "right")
        self.assertEqual(motion_direction((10, 10), (12, 9)), "still/unclear")

    def test_category_counts(self):
        self.assertEqual(frame_counts([{"class": "car"}, {"class": "person"}, {"class": "bus"}])["vehicles"], 2)

    def test_long_analysis_and_csv(self):
        # Video is > 60 seconds even though tiny/fast to decode.
        with tempfile.TemporaryDirectory() as td:
            from video_engine import OUTPUTS
            import video_engine
            old = video_engine.OUTPUTS
            video_engine.OUTPUTS = Path(td) / "outputs"
            try:
                # 65-second clip with 130 frames; fast synthetic for tests.
                clip = Path(td) / "clip.avi"
                create_video(clip, frames=130, fps=2)
                fake = types.ModuleType("ultralytics")
                fake.YOLO = FakeYOLO
                with patch.dict(sys.modules, {"ultralytics": fake, "torch": fake_torch}):
                    job = VideoJob(str(clip), VideoSettings(analysis_fps=1), label="test")
                    job._thread.join(timeout=20)
                snap = job.snapshot()
                self.assertEqual(snap["status"], "completed", snap["error"])
                self.assertGreater(snap["video_second"], 60)
                self.assertGreater(snap["analyzed_frames"], 60)
                self.assertEqual(snap["unique_tracks"], 1)
                self.assertIsNotNone(snap["best_preview_jpeg"])
                self.assertGreater(snap["best_detection_count"], 0)
                self.assertEqual(snap["detected_class_totals"]["car"], snap["analyzed_frames"])
                self.assertEqual(snap["detected_frames"], snap["analyzed_frames"])
                with job.summary_file.open(encoding="utf-8-sig", newline="") as src:
                    self.assertGreater(len(list(csv.DictReader(src))), 60)
                with job.objects_file.open(encoding="utf-8-sig", newline="") as src:
                    obj = next(csv.DictReader(src))
                    self.assertEqual(obj["class"], "car")
                    self.assertIn("image_motion_px_s", obj)
                    self.assertEqual(obj["calibrated_speed_kmh"], "")
                with job.events_file.open(encoding="utf-8-sig", newline="") as src:
                    events = list(csv.DictReader(src))
                    self.assertGreaterEqual(len(events), 1)
                    self.assertEqual(events[0]["event_type"], "low_brightness")
            finally:
                video_engine.OUTPUTS = old

    def test_camera_open_failure_is_reported(self):
        from video_engine import OUTPUTS
        import video_engine
        with tempfile.TemporaryDirectory() as td:
            old = video_engine.OUTPUTS
            video_engine.OUTPUTS = Path(td)
            try:
                class MissingCamera:
                    def isOpened(self): return False
                    def release(self): pass
                fake = types.ModuleType("ultralytics")
                fake.YOLO = FakeYOLO
                with patch.dict(sys.modules, {"ultralytics": fake, "torch": fake_torch}), patch("video_engine.cv2.VideoCapture", return_value=MissingCamera()):
                    job = VideoJob(0, VideoSettings())
                    job._thread.join(timeout=10)
                    self.assertEqual(job.snapshot()["status"], "error")
                    self.assertIn("Cannot open video or camera", job.snapshot()["error"])
            finally:
                video_engine.OUTPUTS = old

if __name__ == "__main__":
    unittest.main()
