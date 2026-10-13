"""Check source-calibrated Three.js JavaScript and projection wiring."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from calibrated_scene_view import HTML


class Surveyed3DViewTests(unittest.TestCase):
    def test_true_source_camera_extrinsics_and_world_trajectories_are_used(self):
        self.assertIn("metric.rotation_cv",HTML)
        self.assertIn("metric.translation_cv",HTML)
        self.assertIn("sourceForward",HTML)
        self.assertIn("const sourceCamera=new T.PerspectiveCamera",HTML)
        self.assertIn("renderer.render(scene,useOrbit?camera:sourceCamera)",HTML)
        self.assertIn("sourceCamera.updateMatrixWorld(true)",HTML)
        self.assertIn("controls.target.copy(sourceTarget)",HTML)
        self.assertIn("new T.PlaneGeometry(metric.width_m,metric.length_m)",HTML)
        self.assertIn("track.points",HTML)
        self.assertIn("p.length>=7",HTML)
        self.assertIn("prev[5]",HTML)
        self.assertIn("1.35",HTML)
        self.assertNotIn("id=\"visualOverlays\"",HTML)

    @unittest.skipUnless(shutil.which("node"),"Node.js not installed")
    def test_source_matched_viewer_is_valid_javascript(self):
        script=re.search(r'<script type="module">([\s\S]*?)</script>',HTML)
        self.assertIsNotNone(script)
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"survey-viewer.mjs"
            file.write_text(script.group(1),encoding="utf-8")
            check=subprocess.run(["node","--check",str(file)],
                                 capture_output=True,text=True,timeout=15)
        self.assertEqual(check.returncode,0,check.stderr)


if __name__=="__main__":unittest.main()
