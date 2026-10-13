"""Camera pose from a truly surveyed planar rectangle can reproject known pixels."""
import unittest
from math import radians,tan
import cv2
import numpy as np

from traffic_geometry import RoadCalibration
from metric_scene import surveyed_road_scene


class MetricPoseTests(unittest.TestCase):
    def test_synthetic_known_camera_pose_and_road_texture(self):
        w,h=960,540
        focal=w/(2*tan(radians(70)/2))
        K=np.array([[focal,0,w/2],[0,focal,h/2],[0,0,1]],np.float64)
        world=np.array([[0,0,0],[8,0,0],[8,25,0],[0,25,0]],np.float64)
        projected,_=cv2.projectPoints(world,np.array([.08,-.04,.05]),
                                      np.array([-3,-12,85],np.float64),K,None)
        pts=tuple((float(x)/w,float(y)/h) for x,y in projected.reshape(-1,2))
        calibration=RoadCalibration(pts,8,25)
        image=np.full((h,w,3),105,dtype=np.uint8)
        result=surveyed_road_scene(image,calibration,70)
        self.assertLess(result["reprojection_rmse_px"],1)
        self.assertAlmostEqual(result["width_m"],8)
        self.assertTrue(result["texture"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(len(result["rotation_cv"]),3)

    def test_invalid_fov_rejected(self):
        cal=RoadCalibration(((.1,.2),(.9,.2),(.9,.8),(.1,.8)),10,100)
        with self.assertRaises(ValueError):
            surveyed_road_scene(np.zeros((120,200,3),np.uint8),cal,15)


if __name__=="__main__":unittest.main()
