"""Validate surveyed perspective calibration and retroactive metric reconstruction."""
import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from math import radians,tan

from traffic_geometry import RoadCalibration
from calibrated_measurements import calibrated_tracks
from reconstruction import build_scene


def known_survey():
    width,height=960,540
    focal=width/(2*tan(radians(70)/2))
    intrinsics=np.array([[focal,0,width/2],[0,focal,height/2],[0,0,1]],np.float64)
    rvec=np.array([.08,-.04,.05]);tvec=np.array([-3.,-12.,85.])
    world=np.array([[0,0,0],[8,0,0],[8,25,0],[0,25,0]],np.float64)
    corners,_=cv2.projectPoints(world,rvec,tvec,intrinsics,None)
    points=tuple((float(x)/width,float(y)/height) for x,y in corners.reshape(-1,2))
    return width,height,RoadCalibration(points,8,25),intrinsics,rvec,tvec


class CalibratedVideoTests(unittest.TestCase):
    def test_true_metric_positions_and_speed_recovered_from_surveyed_camera(self):
        w,h,cal,K,rvec,tvec=known_survey()
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);csvfile=folder/"objects.csv"
            with csvfile.open("w",encoding="utf-8",newline="") as out:
                fields=["video_second","frame_number","track_id","class","confidence",
                        "x1","y1","x2","y2","center_x","world_x_m","world_y_m"]
                writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
                for k in range(51):
                    t=.15*k
                    yy=3+2.4*t
                    p,_=cv2.projectPoints(np.array([[4.,yy,0]],np.float64),rvec,tvec,K,None)
                    x,y=map(float,p.reshape(-1))
                    writer.writerow({
                        "video_second":t,"frame_number":k*4,"track_id":"11",
                        "class":"car","confidence":.95,
                        "x1":x-11,"y1":y-19,"x2":x+11,"y2":y,
                        "center_x":x,"world_x_m":"","world_y_m":""
                    })
            report=calibrated_tracks(csvfile,cal,w,h,min_support=3)
            self.assertEqual(report["accepted_track_count"],1)
            self.assertAlmostEqual(report["tracks"][0]["median_speed_kmh"],8.6,delta=.7)
            self.assertEqual(report["status"],"surveyed_planar_estimates")
            self.assertGreater(report["tracks"][0]["accepted_samples"],10)
            ref=folder/"reference.jpg"
            cv2.imwrite(str(ref),np.full((h,w,3),120,np.uint8))
            job=SimpleNamespace(objects_file=csvfile,reference_frame_file=ref)
            scene=build_scene(job,{
                "frame_width":w,"frame_height":h,
                "video_second":8,
                "calibration":{"points":cal.points,
                               "width_m":cal.width_m,"length_m":cal.length_m},
                "camera_fov_deg":70,
            },include_annotated_video=False)
            self.assertIsNotNone(scene["metric_scene"])
            self.assertEqual(len(scene["tracks"]),1)
            observed=scene["tracks"][0]["points"][10]
            self.assertEqual(len(observed),7)
            self.assertAlmostEqual(observed[5],4,delta=.3)
            self.assertAlmostEqual(observed[6],3+2.4*observed[0],delta=.5)
            self.assertLess(scene["metric_scene"]["reprojection_rmse_px"],1)

    def test_invalid_or_absent_calibration_cannot_report_speed(self):
        w,h,cal,*_=known_survey()
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"detections.csv"
            file.write_text("video_second,track_id,class,confidence,x1,x2,y2\n"
                            "0.0,1,car,.9,40,80,50\n",encoding="utf-8")
            result=calibrated_tracks(file,cal,w,h)
            self.assertIsNone(result["median_track_speed_kmh"])
            with self.assertRaises(ValueError):
                calibrated_tracks(file,cal,0,h)


if __name__=="__main__":unittest.main()
