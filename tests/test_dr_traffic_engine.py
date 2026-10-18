"""Dr Traffic evidence and rule-engine tests; no model weights or video download."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dr_traffic_engine import ReviewSettings, crossed_line, observe_crossings, serialise_json


def car(track, y, height=100):
    return {"class": "car", "track_id": track,
            "bbox": [10, y-20, 60, y], "frame_height": height}


class DrTrafficTests(unittest.TestCase):
    def test_rule_directions(self):
        self.assertTrue(crossed_line(.3, .61, .58, "down"))
        self.assertFalse(crossed_line(.62, .7, .58, "down"))
        self.assertTrue(crossed_line(.8, .52, .58, "up"))
        self.assertFalse(crossed_line(.8, .52, .58, "down"))

    def test_settings_reject_unsupported_models_and_inverted_red_interval(self):
        with self.assertRaises(ValueError):
            ReviewSettings(model_name="unverified.pt").validate()
        with self.assertRaises(ValueError):
            ReviewSettings(manually_verified_red=True, red_start=8, red_end=3).validate()
        ReviewSettings().validate()

    def test_detects_candidate_only_for_manually_marked_red_interval(self):
        s=ReviewSettings(manually_verified_red=True,red_start=1,red_end=4)
        history={}
        self.assertEqual(observe_crossings([car(7,45)],history,video_second=1.2,settings=s),[])
        events=observe_crossings([car(7,65)],history,video_second=2.0,settings=s)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["type"],"possible_red_signal_crossing")
        self.assertEqual(events[0]["signal_status"],"manually_marked_red")
        self.assertFalse(events[0]["confirmed_violation"])
        self.assertEqual(observe_crossings([car(7,70)],history,video_second=2.5,settings=s),[])

    def test_no_red_is_only_line_observation(self):
        settings=ReviewSettings()
        memory={}
        observe_crossings([car(1,30)],memory,video_second=1,settings=settings)
        event=observe_crossings([car(1,75)],memory,video_second=1.5,settings=settings)[0]
        self.assertEqual(event["type"],"line_crossing_observation")
        self.assertNotEqual(event["signal_status"],"verified_red")

    def test_stale_track_cannot_be_used_for_violation(self):
        settings=ReviewSettings(manually_verified_red=True,red_start=1,red_end=30)
        memory={}
        observe_crossings([car(1,30)],memory,video_second=1,settings=settings)
        self.assertEqual(observe_crossings([car(1,75)],memory,video_second=10,settings=settings),[])

    def test_missing_track_id_is_ignored(self):
        self.assertFalse(observe_crossings([car(None,65)],{},video_second=3,settings=ReviewSettings()))

    def test_json_export_never_claims_legal_confirmation(self):
        payload={"status":"completed","events":[{"confirmed_violation":False}]}
        self.assertIn(b'"confirmed_violation": false',serialise_json(payload))


if __name__ == "__main__":
    unittest.main()
