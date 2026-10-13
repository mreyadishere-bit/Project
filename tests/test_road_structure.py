"""Perspective-only line evidence is NOT certified road geometry."""
import unittest
import cv2
import numpy as np
from road_structure import suggest_perspective,draw_perspective_hints


class RoadStructureTests(unittest.TestCase):
    def test_blank_video_returns_no_fabricated_lanes_or_vanishing_point(self):
        image=np.zeros((480,800,3),np.uint8)
        result=suggest_perspective(image)
        self.assertEqual(result["status"],"insufficient_geometry")
        self.assertIsNone(result["vanishing_point_candidate"])
        self.assertEqual(result["line_candidates"],[])

    def test_camera_lines_are_pixel_hypotheses_not_world_measurements(self):
        image=np.full((540,960,3),110,np.uint8)
        # Converging painted-looking lines, plus clutter from the image.
        for x in [40,130,230,720,820,930]:
            cv2.line(image,(x,539),(479,150),(250,250,250),4,cv2.LINE_AA)
        result=suggest_perspective(image)
        self.assertGreater(len(result["line_candidates"]),2)
        self.assertIn("not",result["notes"].lower())
        self.assertNotIn("width_m",result)
        overlay=draw_perspective_hints(image,result)
        self.assertEqual(overlay.shape,image.shape)
        self.assertNotEqual(int(overlay.sum()),int(image.sum()))


if __name__=="__main__":unittest.main()
