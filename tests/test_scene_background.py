"""Camera-registered background extraction regression tests."""
import base64
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from scene_background import background_photo


class SourceBackgroundTests(unittest.TestCase):
    def test_stationary_road_retained_and_moving_vehicle_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            video = folder / "source.avi"
            codec = cv2.VideoWriter_fourcc(*"MJPG")
            output = cv2.VideoWriter(str(video), codec, 10, (96,64))
            if not output.isOpened():
                self.skipTest("MJPG VideoWriter unavailable")
            try:
                for k in range(24):
                    frame = np.zeros((64,96,3),dtype=np.uint8)
                    frame[:,:,:] = [40,75,110]
                    frame[:,25:28] = [195,195,195] # permanent roadside marking
                    x = k*3
                    frame[39:47,x:x+11] = [240,240,240] # vehicle passes across frame
                    output.write(frame)
            finally:
                output.release()
            job = SimpleNamespace(folder=folder,source=str(video),source_kind="file")
            uri,label=background_photo(job,"data:image/jpeg;base64,fallback",width=96,samples=21)
            self.assertIn("Temporal median",label)
            raw=base64.b64decode(uri.split(",",1)[1])
            decoded=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_COLOR)
            self.assertEqual(decoded.shape[:2],(64,96))
            self.assertLess(float(np.abs(decoded[42,60].astype(float)-np.array([40,75,110])).max()),25)
            self.assertGreater(float(decoded[20,26].mean()),160)
            self.assertTrue((folder/"scene_background.jpg").is_file())

    def test_unavailable_file_falls_back_to_source_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            job=SimpleNamespace(folder=Path(tmp),source=str(Path(tmp)/"missing.mov"),source_kind="file")
            uri,label=background_photo(job,"data:image/jpeg;base64,reference")
            self.assertEqual(uri,"data:image/jpeg;base64,reference")
            self.assertIn("Single real",label)


if __name__=="__main__":unittest.main()
