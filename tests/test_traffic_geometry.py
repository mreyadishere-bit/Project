"""Video analytics: line crossing counts are not 'visible now'; geometry is optional."""
import unittest
from traffic_geometry import CrossingCounter,RoadCalibration,ground_kinematics


class LineCountingTests(unittest.TestCase):
    def car(self, ident, y, typ="car"):
        return {"track_id":ident,"class":typ,"x1":10,"y1":y-15,
                "x2":40,"y2":y}

    def test_crossing_counts_once_despite_repeated_frames(self):
        c=CrossingCounter(.5)
        for i,y in enumerate([20,25,35,48,55,65,73,80,40,65]):
            c.observe([self.car(6,y)],100,100,i*.2)
        s=c.snapshot()
        self.assertEqual(s["total_passed"],1)
        self.assertEqual(s["passed_by_class"]["car"],1)
        self.assertEqual(len(c.events),1)

    def test_visible_never_crossed_is_not_passed(self):
        c=CrossingCounter(.5)
        for i in range(10):c.observe([self.car(1,40),self.car(2,34)],100,100,i)
        self.assertEqual(c.snapshot()["total_passed"],0)

    def test_untracked_does_not_become_fake_passes(self):
        c=CrossingCounter(.5)
        for y in (10,90,10):c.observe([self.car("",y)],100,100,1)
        self.assertEqual(c.snapshot()["total_passed"],0)

    def test_multiple_directions(self):
        c=CrossingCounter(.5)
        c.observe([self.car(1,10),self.car(2,90,"truck")],100,100,0)
        c.observe([self.car(1,90),self.car(2,10,"truck")],100,100,1)
        self.assertEqual(c.snapshot()["total_passed"],2)
        self.assertEqual(sum(c.snapshot()["passed_by_direction"].values()),2)

    def test_surveyed_plane_and_heading(self):
        calibration=RoadCalibration(((.1,.1),(.9,.1),(.9,.9),(.1,.9)),8,100)
        a=calibration.world(10,10,100,100)
        b=calibration.world(90,90,100,100)
        self.assertAlmostEqual(a[0],0,places=3)
        self.assertAlmostEqual(b[0],8,places=3)
        speed,angle=ground_kinematics((0,0,0),(0,10),2)
        self.assertAlmostEqual(speed,18)
        self.assertAlmostEqual(angle,90)
        self.assertEqual(ground_kinematics((0,0,0),(900,0),.1),(None,None))

    def test_untrusted_collinear_calibration_rejected(self):
        with self.assertRaises(ValueError):
            RoadCalibration(((0,0),(.2,.2),(.4,.4),(.6,.6)),7,50)


if __name__=="__main__":unittest.main()
