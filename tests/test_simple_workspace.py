"""No-settings hosted home and fixed camera WebGL script smoke coverage."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from road_compare3d import VIEWER


class SimpleWorkspaceTests(unittest.TestCase):
    def test_new_primary_dr_traffic_home(self):
        """The public app now intentionally presents Dr Traffic instead of Smart Road."""
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),default_timeout=45)
        at.run(timeout=40)
        self.assertFalse(at.exception,str(at.exception))
        source=(Path(__file__).resolve().parents[1] / "dr_traffic_app.py").read_text(encoding="utf-8")
        self.assertIn("st.file_uploader(",source)
        self.assertIn("Analyze traffic video",source)
        self.assertTrue(any("Analyze traffic video" in b.label for b in at.button))

    def test_hosted_auto_profiles_are_accepted_by_video_engine(self):
        """Both hardware profiles must be accepted before starting a worker."""
        import sys
        import types
        from unittest.mock import patch
        import video_engine
        from simple_workspace import _automatic_settings

        with tempfile.TemporaryDirectory() as td:
            with patch.object(video_engine, "OUTPUTS", Path(td)), \
                    patch("video_engine.threading.Thread") as mocked_thread:
                for has_gpu in (False, True):
                    with self.subTest(gpu=has_gpu):
                        fake_torch = types.SimpleNamespace(
                            cuda=types.SimpleNamespace(is_available=lambda: has_gpu)
                        )
                        with patch.dict(sys.modules, {"torch": fake_torch}):
                            settings = _automatic_settings()
                            job = video_engine.VideoJob("sample.mp4", settings)
                        mocked_thread.return_value.start.assert_called()
                        self.assertEqual(job.settings, settings)
                        self.assertEqual(settings.analysis_fps, 10 if has_gpu else 3)
                        self.assertEqual(settings.detail_scan_every, 8 if has_gpu else 14)

    @unittest.skipUnless(shutil.which("node"),"Node runtime missing")
    def test_scene_javascript_parses(self):
        m=re.search(r'<script type="module">([\s\S]*?)</script>',VIEWER)
        self.assertIsNotNone(m)
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"scene.mjs"
            file.write_text(m.group(1),encoding="utf-8")
            check=subprocess.run(["node","--check",str(file)],capture_output=True,text=True,timeout=15)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_original_footage_and_one_real_3d_model(self):
        self.assertIn('<video id="sourceVideo"',VIEWER)
        self.assertIn('video.currentTime',VIEWER)
        self.assertIn('sourceCamera',VIEWER)
        self.assertIn('imageToGround',VIEWER)
        self.assertIn('OrbitControls',VIEWER)
        self.assertIn('PerspectiveCamera',VIEWER)
        self.assertIn('CylinderGeometry',VIEWER)
        self.assertIn('vehicleModel',VIEWER)
        self.assertIn('3D top view',VIEWER)
        self.assertIn('Original recorded video',VIEWER)
        self.assertIn('id="matchedBackground"', VIEWER)
        self.assertIn('environment.visible=!aligned', VIEWER)
        self.assertIn('backgroundImage', VIEWER)
        self.assertIn('videoCtx.drawImage(video,0,0,frameWidth,frameHeight)', VIEWER)
        self.assertIn('id="visualOverlays"', VIEWER)
        self.assertIn('data.roadContext!=="highway_hint"', VIEWER)
        self.assertIn('document.getElementById("whatObserved").textContent', VIEWER)
        self.assertIn('sourceTexture', VIEWER)
        self.assertIn('video.currentTime', VIEWER)

        self.assertNotIn('Observed trajectories',VIEWER)
        self.assertNotIn('id="before"',VIEWER)
        self.assertNotIn('requestAnimationFrame(frame)',VIEWER)

if __name__=="__main__":unittest.main()
