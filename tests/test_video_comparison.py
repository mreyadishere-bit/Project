"""Original-video comparator tests: video bytes are original, bounded and private."""
import base64
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from video_comparison import prepare_source_video,source_video_path


class OriginalComparisonVideoTests(unittest.TestCase):
    def test_source_only_for_recorded_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"street.mov"
            path.write_bytes(b"FAKE")
            job=SimpleNamespace(source=path,source_kind="file")
            self.assertEqual(source_video_path(job),path)
            job.source_kind="public_live"
            self.assertIsNone(source_video_path(job))

    def test_no_source_requires_local_picker(self):
        with tempfile.TemporaryDirectory() as temp:
            job=SimpleNamespace(source=Path(temp)/"missing.mov",
                                folder=Path(temp),source_kind="file")
            url,message=prepare_source_video(job)
            self.assertIsNone(url)
            self.assertIn("Original",message)

    @unittest.skipUnless(shutil.which("ffmpeg"),"ffmpeg not installed")
    def test_private_original_mov_to_browser_h264(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            source=directory/"sample.mov"
            # Small synthetic video; original is NOT annotated by YOLO.
            make=subprocess.run([
                "ffmpeg","-y","-hide_banner","-loglevel","error",
                "-f","lavfi","-i","color=c=blue:s=128x72:r=12:d=1",
                "-c:v","mpeg4","-q:v","8",str(source)
            ],capture_output=True,timeout=18)
            self.assertEqual(make.returncode,0,make.stderr)
            job=SimpleNamespace(source=str(source),source_kind="file",folder=directory)
            uri,note=prepare_source_video(job)
            self.assertTrue(uri.startswith("data:video/mp4;base64,"))
            self.assertIn("original footage",note)
            output=base64.b64decode(uri.split(",",1)[1])
            self.assertGreater(len(output),256)
            self.assertIn(b"ftyp",output[:128])
            self.assertEqual((directory/"comparison_original.mp4").read_bytes(),output)
            # Reuse cached encoded media; doesn't recompress it.
            with patch("video_comparison.subprocess.run",side_effect=AssertionError("re-encoded")):
                again,_=prepare_source_video(job)
            self.assertEqual(uri,again)
            large,_=prepare_source_video(job,max_inline_bytes=32)
            self.assertIsNone(large)

if __name__=="__main__":unittest.main()
