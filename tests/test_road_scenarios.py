"""Clear user-facing, evidence-gated roadway scenario tests."""
import unittest
from road_scenarios import make_scenarios, candidate_site_review

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

    def test_field_study_grounded_in_separate_video_moments(self):
        events=[
            {"video_second":5.0,"frame_count":5},
            {"video_second":5.5,"frame_count":4},
            {"video_second":11.2,"frame_count":6},
        ]
        review=candidate_site_review(events,{"analyzed_frames":90})
        self.assertIsNotNone(review)
        self.assertIn("5.0s",review["evidence"])
        self.assertIn("11.2s",review["evidence"])
        self.assertIn("on-site review",review["action"])
        self.assertIn("not measured",review["evidence"])
        self.assertEqual(review["simulation_option"],"signal_concept")

    def test_one_or_weak_interaction_never_auto_recommends_crossing(self):
        self.assertIsNone(candidate_site_review(
            [{"video_second":5.1,"frame_count":7}],{"analyzed_frames":200}))
        self.assertIsNone(candidate_site_review(
            [{"video_second":5.1,"frame_count":2},
             {"video_second":12,"frame_count":1}],{"analyzed_frames":200}))
        self.assertIsNone(candidate_site_review(
            [{"video_second":5.1,"frame_count":5},
             {"video_second":9.1,"frame_count":6}],{"analyzed_frames":3}))

    def test_flow_trails_require_observed_vehicles(self):
        result=make_scenarios(report(),{"analyzed_frames":50,
               "percent_of_sampled_frames":{"vehicles":65},"averages_per_frame":{"vehicles":3}})
        self.assertEqual(result["initial"],"flow")
        self.assertIn("tracks",result["scenarios"][0]["claim"].lower())

if __name__=="__main__":unittest.main()
