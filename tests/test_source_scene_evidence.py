"""Grounded road-scene evidence never invents a generic road safety design."""
import csv
import tempfile
import unittest
from pathlib import Path
import cv2
import numpy as np
from source_scene_evidence import stationary_review_candidates, review_moments
from source_scene_view import highlight_photo, _source_frame


class SourceSceneEvidenceTests(unittest.TestCase):
    def _file(self,path,rows):
        fields=["video_second","frame_number","class","track_id","confidence",
                "x1","x2","y1","y2","center_x"]
        with Path(path).open("w",newline="",encoding="utf-8") as out:
            writer=csv.DictWriter(out,fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_stationary_car_has_real_time_and_image_location_but_not_illegal_parking_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            csvfile=Path(folder)/"objects.csv"
            rows=[{
                "video_second":i*.5,"frame_number":i*12,"class":"car",
                "track_id":"123","confidence":.92,
                "x1":103+i*.10,"x2":164+i*.10,"y1":190,"y2":270+i*.11,
                "center_x":133+i*.10
            } for i in range(15)]
            self._file(csvfile,rows)
            events=stationary_review_candidates(csvfile,640,480)
            self.assertEqual(len(events),1)
            self.assertAlmostEqual(events[0]["video_second"],3.5,delta=.2)
            self.assertIn("not proof",events[0]["explanation"].lower())
            combined=review_moments([],events)
            self.assertEqual(len(combined),1)
            self.assertTrue(0<combined[0]["image_location"][0]<1)
            self.assertIn("loading area",combined[0]["review_action"])

    def test_moving_car_never_flagged_as_stationary(self):
        with tempfile.TemporaryDirectory() as folder:
            csvfile=Path(folder)/"objects.csv"
            rows=[{
                "video_second":i*.4,"frame_number":i*10,"class":"car",
                "track_id":"41","confidence":.90,
                "x1":100+12*i,"x2":158+12*i,"y1":210,
                "y2":292,"center_x":129+12*i,
            } for i in range(11)]
            self._file(csvfile,rows)
            self.assertEqual(stationary_review_candidates(csvfile,640,480),[])

    def test_real_original_frame_selected_and_annotated_without_fabricated_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            video=Path(folder)/"source.avi"
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"MJPG"),6,(320,180))
            self.assertTrue(writer.isOpened())
            for i in range(36):
                image=np.full((180,320,3),(60+i,115,90),np.uint8)
                writer.write(image)
            writer.release()
            data=_source_frame(str(video),video.stat().st_size,
                               video.stat().st_mtime_ns,2.0)
            self.assertIsNotNone(data)
            image=highlight_photo(data,[.5,.65],"CHECK EVENT")
            self.assertEqual(image.shape[:2],(180,320))
            self.assertGreater(int(image.sum()),0)
            with self.assertRaises(ValueError):
                highlight_photo(data,[1.2,.5],"OUTSIDE")

    def test_review_items_require_real_grounded_coordinates(self):
        events=[{
            "video_second":6.4,"image_location":(.4,.7),
            "frame_count":6
        }]
        result=review_moments(events,[])
        self.assertEqual(len(result),1)
        self.assertIn("crossing demand",result[0]["review_action"])
        self.assertNotIn("certified",str(result).lower())


if __name__=="__main__":unittest.main()
