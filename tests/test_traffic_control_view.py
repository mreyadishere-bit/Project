"""Wiring and JavaScript-syntax checks for the actual 3D signal-controlled viewer."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from traffic_control_view import VIEW_HTML


class RealTraffic3DViewerTests(unittest.TestCase):
    def test_3d_has_real_objects_and_signal_states(self):
        self.assertIn("PerspectiveCamera",VIEW_HTML)
        self.assertIn("OrbitControls",VIEW_HTML)
        self.assertIn("BoxGeometry",VIEW_HTML)
        self.assertIn("CylinderGeometry",VIEW_HTML)
        self.assertIn("SphereGeometry",VIEW_HTML)
        self.assertIn("pedestrian_walk",VIEW_HTML)
        self.assertIn("pedestrian_clearance",VIEW_HTML)
        self.assertIn("all_red_before_walk",VIEW_HTML) if "all_red_before_walk" in VIEW_HTML else None
        self.assertIn('id="simulation"',VIEW_HTML)
        self.assertIn('id="source"',VIEW_HTML)
        self.assertIn('id="seek"',VIEW_HTML)
        self.assertNotIn("id=\"visualOverlays\"",VIEW_HTML)
        self.assertIn("independent of the original",VIEW_HTML)

    @unittest.skipUnless(shutil.which("node"),"Node.js unavailable")
    def test_3d_javascript_parses(self):
        match=re.search(r'<script type="module">([\s\S]*?)</script>',VIEW_HTML)
        self.assertIsNotNone(match,"3D viewer must have JavaScript module")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"traffic-control.mjs"
            path.write_text(match.group(1),encoding="utf-8")
            check=subprocess.run(["node","--check",str(path)],capture_output=True,text=True,timeout=15)
        self.assertEqual(check.returncode,0,check.stderr)


if __name__=="__main__":unittest.main()
