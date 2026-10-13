"""Validate in-page Three.js rendering code syntax without downloading CDN modules."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reconstruction_ui import HTML


class ReconstructionJavascriptTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"),"NodeJS not available")
    def test_interactive_3d_module_compiles(self):
        pattern=r'<script type="module">([\s\S]*?)</script>'
        found=re.search(pattern,HTML)
        self.assertIsNotNone(found,"Expected embedded Three.js scene module")
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"road-viewer.mjs"
            path.write_text(found.group(1),encoding="utf-8")
            check=subprocess.run(["node","--check",str(path)],capture_output=True,
                                 text=True,timeout=15)
            self.assertEqual(check.returncode,0,check.stderr)

    def test_replay_has_explicit_interactive_controls(self):
        for selector in ('id="speed"','id="width"','id="crossing"',
                         'id="seek"','id="pause"','id="reset"','id="apply"'):
            self.assertIn(selector,HTML)


if __name__=="__main__":unittest.main()
