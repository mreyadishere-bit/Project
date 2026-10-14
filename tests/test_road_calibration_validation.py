import unittest
from traffic_geometry import RoadCalibration
from road_calibration_validation import validate_checkpoint

class IndependentCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.cal=RoadCalibration(((.2,.8),(.8,.8),(.65,.3),(.35,.3)),8.,40.)

    def test_consistent_fifth_point_passes(self):
        # A fresh image location is independently surveyed in the same plane.
        x,y=.5,.58
        truth=self.cal.world(x*1000,y*750,1000,750)
        out=validate_checkpoint(self.cal,(x,y),truth,1000,750)
        self.assertEqual(out["status"],"independently_checked")
        self.assertLess(out["error_m"],.001)

    def test_false_surveyed_point_fails_even_though_four_corners_fit(self):
        x,y=.5,.58
        truth=self.cal.world(x*1000,y*750,1000,750)
        out=validate_checkpoint(self.cal,(x,y),(truth[0]+2.,truth[1]),1000,750)
        self.assertEqual(out["status"],"failed_independent_check")
        self.assertGreater(out["error_m"],1.5)

    def test_fifth_point_cannot_reuse_a_fitted_corner(self):
        with self.assertRaisesRegex(ValueError,"independent"):
            validate_checkpoint(self.cal,(.2,.8),(0,0),1000,750)

    def test_outside_surveyed_patch_rejected(self):
        with self.assertRaises(ValueError):
            validate_checkpoint(self.cal,(.5,.58),(100,500),1000,750)

if __name__=="__main__":unittest.main()
