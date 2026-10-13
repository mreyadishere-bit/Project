"""Image-plane analysis regressions; intentionally no claim of collision prediction."""
import unittest
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scene_intelligence import image_motion, scene_diagnostics, diagnostic_events, visual_proximity, draw_scene_overlay


class SceneIntelligenceTests(unittest.TestCase):
    def test_motion_requires_prior_frame_and_positive_time(self):
        self.assertEqual(image_motion(None, (10, 10), 2), (None, None))
        self.assertEqual(image_motion((0, 0, 2), (10, 10), 2), (None, None))

    def test_no_fake_metric_speed_without_scale(self):
        px_s, kmh = image_motion((0, 0, 0), (30, 40), 2)
        self.assertAlmostEqual(px_s, 25.0)
        self.assertIsNone(kmh)

    def test_calibrated_speed_is_explicit_approximation(self):
        px_s, kmh = image_motion((0, 0, 0), (30, 40), 2, 0.1)
        self.assertAlmostEqual(px_s, 25.0)
        self.assertAlmostEqual(kmh, 9.0)

    def test_visual_proximity_uses_image_coords_not_real_distance(self):
        objects = [
            {"class": "person", "x1": 45, "y1": 20, "x2": 55, "y2": 60, "track_id": 7},
            {"class": "car", "x1": 40, "y1": 30, "x2": 60, "y2": 60, "track_id": 9},
        ]
        result = visual_proximity(objects, 100, 100)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["vehicle_id"], 9)

    def test_diagnostics_are_bounded_and_not_accident_scores(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        detections = [{"class": "car", "x1": 1, "y1": 1, "x2": 40, "y2": 40}]
        diag = scene_diagnostics(image, detections, {"vehicles": 1})
        self.assertTrue(diag["low_image_brightness"])
        self.assertGreater(diag["occupancy_ratio"], 0)
        self.assertFalse(diag["dense_scene"])

    def test_branded_video_overlay_draws_without_mutating_frame(self):
        image = np.zeros((120, 160, 3), dtype=np.uint8)
        objects = [{
            "class": "car", "x1": 20, "y1": 20, "x2": 90, "y2": 100,
            "track_id": 4, "confidence": .87, "calibrated_speed_kmh": None
        }]
        output = draw_scene_overlay(image, objects)
        self.assertTrue(np.any(output != image))
        self.assertFalse(np.any(image))

    def test_event_cooldown(self):
        d = {"low_image_brightness": True, "dense_scene": False, "visual_proximity_pairs": 0}
        emitted = {}
        self.assertEqual(len(diagnostic_events(d, 0, emitted)), 1)
        self.assertEqual(len(diagnostic_events(d, 5, emitted)), 0)
        self.assertEqual(len(diagnostic_events(d, 13, emitted)), 1)


if __name__ == "__main__":
    unittest.main()
