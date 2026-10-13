"""Clear user-facing, evidence-gated roadway scenario tests."""
import unittest
from road_scenarios import make_scenarios

def report():
    return {"recommendations":[]}

class RoadScenariosTest(unittest.TestCase):
    def test_night_scene_visibility_labels_camera_exposure_not_streetlight_simulation(self):
        evidence={"analyzed_frames":120,"percent_of_sampled_frames":{"dark_image":38,"vehicles":90,"pedestrians":8},
                  "averages_per_frame":{"vehicles":4}}
        result=make_scenarios(report(),evidence)
        self.assertEqual(result["initial"],"visibility")
        visibility=result["scenarios"][0]
        self.assertTrue(visibility["evidence_based"])
        self.assertIn("exposure",visibility["claim"])
        self.assertIn("not",visibility["claim"].lower())
        self.assertIn("Measure real lighting",visibility["validate"])

    def test_pedestrian_case_only_highlights_observations_not_proposed_crossing(self):
        evidence={"analyzed_frames":50,"percent_of_sampled_frames":{"vehicles":75,"pedestrians":34,"close_in_image":12},
                  "averages_per_frame":{"vehicles":3}}
        result=make_scenarios(report(),evidence)
        self.assertEqual(result["initial"],"pedestrians")
        self.assertIn("NOT automatically",result["scenarios"][0]["validate"])
        self.assertNotIn("build a crossing",str(result))

    def test_sparse_scene_does_not_invent_road_safety_solution(self):
        result=make_scenarios(report(),{"analyzed_frames":6})
        self.assertEqual(result["initial"],"inspection")
        self.assertFalse(result["scenarios"][0]["evidence_based"])
        self.assertIn("not sufficient",result["scenarios"][0]["why"])

    def test_flow_trails_require_observed_vehicles(self):
        result=make_scenarios(report(),{"analyzed_frames":50,
               "percent_of_sampled_frames":{"vehicles":65},"averages_per_frame":{"vehicles":3}})
        self.assertEqual(result["initial"],"flow")
        self.assertIn("tracks",result["scenarios"][0]["claim"].lower())

if __name__=="__main__":unittest.main()
