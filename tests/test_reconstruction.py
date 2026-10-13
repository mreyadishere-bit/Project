"""Time-indexed scene export uses real observed tracking rows."""
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from reconstruction import build_scene


class ReconstructionTests(unittest.TestCase):
    def test_preview_spans_video_timeline_and_contains_reference_photo(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            frame=np.zeros((120,200,3),dtype=np.uint8)
            frame[:,:,:]=[15,55,120]
            jpg=p/"frame.jpg"
            cv2.imwrite(str(jpg),frame)
            csvpath=p/"objects.csv"
            with csvpath.open("w",encoding="utf-8",newline="") as stream:
                cols=["video_second","track_id","class","center_x","y2","x1","x2","y1","world_x_m","world_y_m"]
                out=csv.DictWriter(stream,fieldnames=cols)
                out.writeheader()
                for t in range(100):
                    out.writerow(dict(video_second=t,track_id=5,**{"class":"car"},center_x=50+t,
                                     y2=60,x1=30+t,x2=70+t,y1=30,
                                     world_x_m="",world_y_m=""))
            job=SimpleNamespace(objects_file=csvpath,reference_frame_file=jpg)
            scene=build_scene(job,{"frame_width":200,"frame_height":120,
                                    "video_second":99,"crossings":{"line_y_fraction":.5}})
            self.assertTrue(scene["image"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(len(scene["tracks"]),1)
            points=scene["tracks"][0]["points"]
            self.assertEqual(points[0][0],0)
            self.assertEqual(points[-1][0],99)
            self.assertEqual(scene["line"],.5)

    def test_no_reference_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_scene(SimpleNamespace(objects_file=Path(tmp)/"missing.csv"),{"frame_width":300,"frame_height":100})


if __name__=="__main__":unittest.main()
