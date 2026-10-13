"""Regression tests for complete-video statistics and honest advice."""
import unittest
from insight_engine import EvidenceAccumulator, explain_video, review_priority, suggestions


class InsightTests(unittest.TestCase):
    def test_empty_video_must_not_invent_safety_score(self):
        e=EvidenceAccumulator().snapshot()
        self.assertIsNone(review_priority(e)["score"])
        self.assertIn("No video evidence", explain_video(e,"camera")["headline"])

    def test_full_video_summary_not_just_last_frame(self):
        e=EvidenceAccumulator()
        for i in range(100):
            d=[]
            if i < 80:
                d=[{"class":"car","track_id":12,"x1":10,"y1":10,"x2":70,"y2":70,
                    "image_motion_px_s":20}]
            counts={"vehicles":len(d),"people":0}
            diag={"brightness":155, "low_image_brightness":False,
                  "visual_proximity_pairs":0,"dense_scene":False}
            e.observe(d,counts,diag,second=float(i),frame_width=200,frame_height=100)
        s=e.snapshot()
        self.assertEqual(s["analyzed_frames"],100)
        self.assertAlmostEqual(s["averages_per_frame"]["vehicles"],.8)
        self.assertEqual(s["unique_track_ids_by_class"]["car"],1)
        self.assertEqual(s["percent_of_sampled_frames"]["vehicles"],80.0)
        self.assertEqual(s["footpoint_activity_grid"][5][2],80)
        self.assertEqual(len(suggestions(s)),1)
        self.assertEqual(suggestions(s)[0]["id"],"routine")

    def test_actual_triggered_rules_require_evidence(self):
        e=EvidenceAccumulator()
        for i in range(50):
            detections=[
                {"class":"car","track_id":1,"x1":0,"y1":1,"x2":50,"y2":51},
                {"class":"person","track_id":2,"x1":20,"y1":1,"x2":39,"y2":49},
            ]
            diag={"brightness":32,"low_image_brightness":True,
                  "visual_proximity_pairs":1,"dense_scene":False}
            e.observe(detections,{"vehicles":1,"people":1},diag,second=float(i),
                      frame_width=150,frame_height=75)
        report=explain_video(e.snapshot(),"street")
        ids={r["id"] for r in report["recommendations"]}
        self.assertIn("crossing_review",ids)
        self.assertIn("lighting_review",ids)
        self.assertIn("speed_review",ids)
        self.assertLessEqual(report["priority"]["score"],100)
        self.assertIn("NOT accident risk",report["priority"]["explanation"])


if __name__=="__main__":
    unittest.main()
