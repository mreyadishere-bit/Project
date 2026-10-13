"""Smoke-test a completed analysis on the actual Streamlit results screen."""
from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest


class ResultsUISmokeTests(unittest.TestCase):
    def test_completed_evidence_page_with_simulator(self):
        # No need to download a YOLO model: the UI should render with
        # a completed evidence bundle assembled from typed fixture data.
        src = r'''
import streamlit as st
from pathlib import Path
from types import SimpleNamespace
from results_ui import results_page
st.set_page_config(layout="wide")
p=Path("this_file_should_not_exist_results_test.csv")
evidence={
    "analyzed_frames":100,
    "averages_per_frame":{"vehicles":2.4,"people":0.5},
    "percent_of_sampled_frames":{
        "vehicles":90., "pedestrians":40., "dark_image":0.,
        "close_in_image":10.,"crowded_image":12.
    },
    "average_image_brightness":140.0,
    "mean_image_motion_px_s":10.0,
    "unique_track_ids_by_class":{"car":4,"person":3},
    "sampled_frame_detections_by_class":{"car":240,"person":50},
    "diagnostic_event_counts":{"visual_proximity":3},
    "footpoint_activity_grid":[[0]*14 for _ in range(8)],
    "hotspot":None,
}
snap={
    "status":"completed", "label":"Synthetic traffic test",
    "analyzed_frames":100,"evidence":evidence,
    "best_preview_jpeg":None,"preview_jpeg":None,
    "video_ready":False,"video_export_error":None,
    "settings_fps":5,
}
job=SimpleNamespace(
    settings=SimpleNamespace(save_video=False),
    id="test-ui-id",video_file=Path("fake-video.mp4"),
    summary_file=p, objects_file=p, events_file=p
)
results_page(job,snap,hosted=True)
'''
        result = AppTest.from_string(src).run(timeout=40)
        self.assertFalse(result.exception, str(result.exception))
        self.assertGreater(len(result.slider), 0)
        self.assertGreater(len(result.checkbox), 0)
        # The Play/Pause controls live inside the standalone animated iframe,
        # so they are not Streamlit native buttons returned by AppTest.


if __name__=="__main__":
    unittest.main()
