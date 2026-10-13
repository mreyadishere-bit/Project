"""Grounded road advice tests: no speculative infrastructure or speed claims."""
import csv
import tempfile
import unittest
from pathlib import Path
from road_advice import road_report,context_from_source,trajectory_evidence


def evidence(frames=120, vehicle=90, person=0, nearby=0, crowd=0, dark=0, avg=3):
    return {"analyzed_frames":frames,
            "percent_of_sampled_frames":{
                "vehicles":vehicle,"pedestrians":person,"close_in_image":nearby,
                "crowded_image":crowd,"dark_image":dark},
            "averages_per_frame":{"vehicles":avg,"people":0},
            "unique_track_ids_by_class":{"car":12}}


class RecommendationsTests(unittest.TestCase):
    def make_tracks(self,folder,count=8):
        p=Path(folder)/"objects.csv"
        fields=["class","track_id","center_x","center_y","video_second","calibrated_speed_kmh"]
        with p.open("w",encoding="utf-8",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for i in range(count):
                for sec in range(8):
                    writer.writerow({"class":"car","track_id":i,"center_x":15+sec*2,
                                     "center_y":20+sec*3,"video_second":sec,"calibrated_speed_kmh":""})
        return p

    def test_highway_never_auto_adds_pedestrian_crosswalk(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_tracks(d)
            report=road_report(evidence(person=85,nearby=90,crowd=30),
                              "vecteezy_flow_of_cars_on_highway.mov",p)
        titles=" ".join(r["title"] for r in report["recommendations"]).lower()
        self.assertNotIn("pedestrian crossing",titles)
        self.assertNotIn("speed limit",titles)
        self.assertFalse(any(r["simulation_option"]=="crossing" for r in report["recommendations"]))
        self.assertEqual(report["context"]["kind"],"unknown")
        self.assertEqual(report["context"]["source_title_hint"],"highway")
        self.assertFalse(report["context"]["pedestrian_infrastructure_claim_allowed"])

    def test_unknown_road_not_forced_to_crosswalk(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_tracks(d)
            report=road_report(evidence(person=85,nearby=80),"street.mov",p)
        self.assertFalse(any(r["simulation_option"]=="crossing" for r in report["recommendations"]))

    def test_no_calibration_no_speed_limit_suggestion(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_tracks(d)
            report=road_report(evidence(crowd=35),"motorway_clip.mov",p)
        self.assertFalse(any(r["simulation_option"]=="speed_review" for r in report["recommendations"]))

    def test_sparse_video_advises_verification(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_tracks(d,0)
            report=road_report(evidence(frames=6,vehicle=0),"highway.mov",p)
        self.assertEqual(report["recommendations"][0]["id"],"collect_evidence")

    def test_evidence_math_is_derived_from_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.make_tracks(d,4)
            result=trajectory_evidence(p)
        self.assertEqual(result["tracks"],4)
        self.assertEqual(result["speed_samples"],0)
        self.assertIsNone(result["speed_kmh_median"])


if __name__=="__main__":unittest.main()
