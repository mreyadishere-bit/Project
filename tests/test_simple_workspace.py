"""No-settings hosted home and fixed camera WebGL script smoke coverage."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from stable_scene import VIEWER


class SimpleWorkspaceTests(unittest.TestCase):
    def test_upload_is_only_configuration_in_home(self):
        at=AppTest.from_file("app.py",default_timeout=45)
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{"SMART_ROAD_HOSTED":"1"}):
            at.run(timeout=40)
        self.assertFalse(at.exception,str(at.exception))
        self.assertEqual(len(at.file_uploader),1)
        self.assertEqual(len(at.slider),0)
        self.assertEqual(len(at.radio),0)
        self.assertIn("Understand any road video",str(at.title))

    @unittest.skipUnless(shutil.which("node"),"Node runtime missing")
    def test_scene_javascript_parses(self):
        m=re.search(r'<script type="module">([\s\S]*?)</script>',VIEWER)
        self.assertIsNotNone(m)
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"scene.mjs"
            file.write_text(m.group(1),encoding="utf-8")
            check=subprocess.run(["node","--check",str(file)],capture_output=True,text=True,timeout=15)
        self.assertEqual(check.returncode,0,check.stderr)

    def test_no_rotating_flat_image_scene(self):
        self.assertNotIn("OrbitControls",VIEWER)
        self.assertNotIn("PlaneGeometry(W,H)",VIEWER)
        self.assertIn("backgroundImage",VIEWER)

if __name__=="__main__":unittest.main()
