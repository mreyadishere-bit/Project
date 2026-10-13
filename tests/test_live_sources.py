"""Validate public YouTube live links and graceful extractor failures offline."""
import sys
import time
import types
import unittest
from unittest.mock import patch

from live_sources import canonical_youtube_live_url, resolve_youtube_live, choose_frame_stream


class YouTubeLinkTests(unittest.TestCase):
    def test_canonical_video_links(self):
        video_id = "jfKfPfyJRdk"
        for url in (
            "https://www.youtube.com/watch?v=" + video_id,
            "https://youtu.be/" + video_id,
            "https://youtube.com/live/" + video_id + "?feature=share",
        ):
            self.assertEqual(canonical_youtube_live_url(url),
                             "https://www.youtube.com/watch?v=" + video_id)

    def test_refuses_arbitrary_url_and_urls_with_credentials(self):
        bad = [
            "http://www.youtube.com/watch?v=jfKfPfyJRdk",
            "https://www.youtube.com.evil.com/watch?v=jfKfPfyJRdk",
            "https://127.0.0.1/private.m3u8",
            "https://evil@youtube.com/watch?v=jfKfPfyJRdk",
            "https://www.youtube.com/@channel/live",
            "file:///etc/passwd", "https://youtu.be/bad",
            "https://youtube.com:443/watch?v=jfKfPfyJRdk",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_youtube_live_url(url)

    def test_live_metadata_is_required(self):
        module = types.ModuleType("yt_dlp")
        class FakeYDL:
            def __init__(self, opts): self.opts = opts
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def extract_info(self, url, download):
                self.url = url
                return {"is_live": False, "live_status": "not_live", "url": "https://example.org/clip.mp4"}
        module.YoutubeDL = FakeYDL
        with patch.dict(sys.modules, {"yt_dlp": module}):
            with self.assertRaisesRegex(ValueError, "not currently live"):
                resolve_youtube_live("https://youtu.be/jfKfPfyJRdk")

    def test_youtube_antibot_error_is_clear_without_authentication_advice(self):
        module = types.ModuleType("yt_dlp")
        class FakeYDL:
            def __init__(self, opts): pass
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def extract_info(self, url, download=False):
                raise RuntimeError("Sign in to confirm you're not a bot")
        module.YoutubeDL = FakeYDL
        with patch.dict(sys.modules, {"yt_dlp": module}):
            with self.assertRaisesRegex(RuntimeError, "blocked automated video access"):
                resolve_youtube_live("https://www.youtube.com/watch?v=FWvIPfxK5Jo")

    def test_selects_hls_video_not_audio_or_dash_fragments(self):
        info = {"formats": [
            {"url": "https://media.example/audio", "protocol": "m3u8_native",
             "vcodec": "none", "height": 0},
            {"url": "https://media.example/dash", "protocol": "http_dash_segments",
             "vcodec": "avc1", "height": 480, "fragments": [{"url": "/chunk"}]},
            {"url": "https://media.example/high.m3u8", "protocol": "m3u8_native",
             "vcodec": "avc1", "height": 1080},
            {"url": "https://media.example/low.m3u8", "protocol": "m3u8_native",
             "vcodec": "avc1", "height": 480},
        ]}
        self.assertEqual(choose_frame_stream(info), "https://media.example/low.m3u8")

    def test_can_select_progressive_video_if_no_hls(self):
        info = {"formats": [
            {"url": "https://media.example/video.mp4", "protocol": "https",
             "vcodec": "avc1", "height": 720}
        ]}
        self.assertEqual(choose_frame_stream(info), "https://media.example/video.mp4")

    def test_rejects_zero_available_video_formats(self):
        for info in ({"formats": []}, {"formats": [
            {"url": "https://media.example/a", "protocol": "m3u8", "vcodec": "none"}
        ]}):
            with self.subTest(info=info), self.assertRaisesRegex(RuntimeError, "did not provide"):
                choose_frame_stream(info)

    def test_live_with_empty_formats_fails_with_precise_message(self):
        module = types.ModuleType("yt_dlp")
        class FakeYDL:
            def __init__(self, opts):
                self.opts = opts
                self.__class__.last_opts = opts
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def extract_info(self, url, download=False):
                return {"id": "FWvIPfxK5Jo", "formats": [], "live_status": None}
        module.YoutubeDL = FakeYDL
        with patch.dict(sys.modules, {"yt_dlp": module}):
            with self.assertRaisesRegex(RuntimeError, "did not provide a usable video stream"):
                resolve_youtube_live("https://www.youtube.com/watch?v=FWvIPfxK5Jo")
        self.assertTrue(FakeYDL.last_opts["ignore_no_formats_error"])
        self.assertNotIn("format", FakeYDL.last_opts)

    def test_extracts_live_https_stream(self):
        module = types.ModuleType("yt_dlp")
        class FakeYDL:
            def __init__(self, opts): self.opts = opts
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def extract_info(self, url, download):
                return {"is_live": True, "live_status": "is_live",
                        "url": "https://stream.example.com/test.m3u8", "title": "Road Camera"}
        module.YoutubeDL = FakeYDL
        with patch.dict(sys.modules, {"yt_dlp": module}):
            self.assertEqual(resolve_youtube_live("https://youtu.be/jfKfPfyJRdk"),
                             ("https://stream.example.com/test.m3u8", "Road Camera"))



class LiveWorkerTests(unittest.TestCase):
    def test_youtube_stream_processes_fresh_frames_and_stops(self):
        """Integration without network: exercise live worker + AI tracking pipeline."""
        import tempfile
        import time
        from pathlib import Path
        from unittest.mock import patch
        import numpy as np
        import video_engine
        from video_engine import VideoJob, VideoSettings
        class Tensor:
            def __init__(self, data): self.data = data
            def cpu(self): return self
            def int(self): return self
            def tolist(self): return self.data
        class Boxes:
            xyxy = Tensor([[10, 12, 70, 65]])
            conf = Tensor([.92])
            cls = Tensor([2])
            id = Tensor([11])
            def __len__(self): return 1
        class Result:
            boxes = Boxes()
            names = {2: "car"}
        class YOLO:
            names = {2: "car"}
            def __init__(self, model): pass
            def track(self, frame, **kwargs): return [Result()]
        class Capture:
            def __init__(self, url, **kwargs): self.closed = False
            def isOpened(self): return True
            def set(self, *args): return True
            def get(self, prop): return 30.0
            def read(self):
                time.sleep(.06)
                return (False, None) if self.closed else (True, np.zeros((100, 130, 3), dtype=np.uint8))
            def release(self): self.closed = True
        fake_yolo = types.ModuleType("ultralytics")
        fake_yolo.YOLO = YOLO
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        with tempfile.TemporaryDirectory() as tmp:
            previous_output = video_engine.OUTPUTS
            video_engine.OUTPUTS = Path(tmp) / "results"
            try:
                with (
                    patch.dict(sys.modules, {"ultralytics": fake_yolo, "torch": fake_torch}),
                    patch("live_sources.resolve_youtube_live",
                          return_value=("https://stream.example.com/live.m3u8", "Public Road")),
                    patch("live_decoder.FFmpegLiveCapture", side_effect=Capture),
                ):
                    for src, kind in (
                        ("https://youtu.be/jfKfPfyJRdk", "youtube"),
                        ("caltrans-sacramento-i5", "public_live"),
                        ("caltrans-district7-cctv101", "public_live"),
                    ):
                        with self.subTest(source=kind, camera=src):
                            job = VideoJob(src, VideoSettings(), source_kind=kind)
                            try:
                                deadline = time.monotonic() + 5
                                while job.snapshot()["analyzed_frames"] < 2 and time.monotonic() < deadline:
                                    time.sleep(.05)
                                self.assertGreaterEqual(job.snapshot()["analyzed_frames"], 2,
                                                        job.snapshot()["error"])
                                self.assertEqual(job.snapshot()["source_kind"], kind)
                                with self.assertRaisesRegex(RuntimeError, "already using"):
                                    VideoJob(src, VideoSettings(), source_kind=kind)
                            finally:
                                job.stop()
                                job._thread.join(timeout=10)
                            self.assertEqual(job.snapshot()["status"], "stopped", job.snapshot()["error"])
                            self.assertGreaterEqual(job.snapshot()["detected_frames"], 2)
            finally:
                video_engine.OUTPUTS = previous_output


if __name__ == "__main__":
    unittest.main()
