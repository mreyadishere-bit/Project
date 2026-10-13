"""Per-vehicle analytics based on full observed CSV with honest calibration gates."""
import csv
import tempfile
import unittest
from pathlib import Path
from traffic_metrics import summarize_tracks,crossing_headways


class MotionMetricsTests(unittest.TestCase):
    def test_unscaled_track_cannot_have_metric_speed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"track.csv"
            with p.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["class","track_id","video_second",
                    "image_motion_px_s","world_x_m","world_y_m","heading_deg"])
                w.writeheader()
                for i in range(4):
                    w.writerow({"class":"car","track_id":7,"video_second":i,
                                "image_motion_px_s":20,
                                "world_x_m":"","world_y_m":"","heading_deg":""})
            data=summarize_tracks(p)
            self.assertEqual(data["rows"],4)
            x=data["tracks"][0]
            self.assertIsNone(x["mean_surveyed_speed_kmh"])
            self.assertEqual(x["mean_image_motion_px_s"],20)
            self.assertEqual(x["observed_seconds"],3)

    def test_known_kinematics_calculate_metric_speed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"track.csv"
            with p.open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["class","track_id","video_second",
                    "image_motion_px_s","world_x_m","world_y_m","heading_deg"])
                w.writeheader()
                for i in range(5):
                    w.writerow({"class":"car","track_id":1,"video_second":i,
                                "world_x_m":i*10,"world_y_m":0,"heading_deg":0,
                                "image_motion_px_s":5})
            x=summarize_tracks(p)["tracks"][0]
            self.assertEqual(x["mean_surveyed_speed_kmh"],36)
            self.assertEqual(x["world_distance_m"],40)

    def test_line_crossing_headway_same_screen_direction(self):
        events=[{"second":1,"direction":"down"},{"second":4,"direction":"down"},
                {"second":5,"direction":"up"},{"second":7,"direction":"down"}]
        v=crossing_headways(events)
        self.assertEqual(v["down"]["mean_gap_seconds"],3)
        self.assertIsNone(v["up"]["mean_gap_seconds"])


if __name__=="__main__":unittest.main()
