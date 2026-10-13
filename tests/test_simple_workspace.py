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
    def test_upload_is_only_configuration_in_home(self):
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"),default_timeout=45)
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{"SMART_ROAD_HOSTED":"1"}):
            at.run(timeout=40)
        self.assertFalse(at.exception,str(at.exception))
        # Streamlit AppTest doesn't expose a public file_uploader interaction
        # API in all supported versions; the upload call is source-inspected
        # while the script is also executed by AppTest.
        from simple_workspace import video_tab
        import inspect
        self.assertIn("st.file_uploader",inspect.getsource(video_tab))
        self.assertEqual(len(at.slider),0)
        self.assertEqual(len(at.radio),0)
        self.assertTrue(at.title)
        self.assertIn("Understand any road video",at.title[0].value)

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
        self.assertIn('Top view',VIEWER)
        self.assertIn('Original recorded video',VIEWER)
        self.assertIn('id="matchedBackground"', VIEWER)
        self.assertIn('environment.visible=!aligned', VIEWER)
        self.assertIn('backgroundImage', VIEWER)
        self.assertIn('sourceTexture', VIEWER)
        self.assertIn('video.currentTime', VIEWER)

        self.assertNotIn('Observed trajectories',VIEWER)
        self.assertNotIn('id="before"',VIEWER)
        self.assertNotIn('requestAnimationFrame(frame)',VIEWER)

if __name__=="__main__":unittest.main()
