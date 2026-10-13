"""Validate public YouTube live links and graceful extractor failures offline."""
import sys
import types
import unittest
from unittest.mock import patch

from live_sources import canonical_youtube_live_url, resolve_youtube_live


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


if __name__ == "__main__":
    unittest.main()
