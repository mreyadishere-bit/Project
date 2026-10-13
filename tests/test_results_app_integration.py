"""Integration smoke of the complete uploaded-video results → event → 3D concept flow."""
import csv
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class EndToEndResultsTests(unittest.TestCase):
    def test_completed_results_and_clicked_three_d_concept_render_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            objects=folder/"objects.csv"
            with objects.open("w",encoding="utf-8",newline="") as file:
                writer=csv.DictWriter(file,fieldnames=[
                    "video_second","frame_number","track_id","class","confidence",
                    "x1","y1","x2","y2","center_x","center_y"
                ])
                writer.writeheader()
                for k in range(10):
                    writer.writerow({
                        "video_second":k*.5,"frame_number":k*12,
                        "track_id":1,"class":"person","confidence":.9,
                        "x1":100,"y1":100,"x2":115,"y2":180,
                        "center_x":107.5,"center_y":140,
                    })
                    writer.writerow({
                        "video_second":k*.5,"frame_number":k*12,
                        "track_id":2,"class":"car","confidence":.88,
                        "x1":102,"y1":110,"x2":145,"y2":183,
                        "center_x":123.5,"center_y":146.5,
                    })
            # Actual Streamlit testing runs the same results function as production.
            script=f'''
from pathlib import Path
from types import SimpleNamespace
from simple_results import show_results
base=Path({str(folder)!r})
job=SimpleNamespace(
 id="test-results",folder=base,
 source_kind="file",source=str(base/"missing-source.mp4"),
 objects_file=base/"objects.csv",summary_file=base/"missing-summary.csv",
 events_file=base/"missing-events.csv",crossings_file=base/"missing-crossings.csv",
 video_file=base/"missing-video.mp4"
)
snap={{
 "label":"sample-urban-video.mp4","status":"completed",
 "video_ready":False,
 "frame_width":800,"frame_height":600,"duration_seconds":5,
 "analyzed_frames":10,"detected_frames":10,"max_vehicles":2,
 "crossings":{{"total_passed":0}},
 "evidence":{{
  "analyzed_frames":10,
  "percent_of_sampled_frames":{{"vehicles":100,"pedestrians":100,"close_in_image":80}},
  "averages_per_frame":{{"vehicles":1}}
 }}
}}
show_results(job,snap)
'''
            app=AppTest.from_string(script).run(timeout=50)
            self.assertFalse(app.exception,
                f"Main completed-video results could not render: {app.exception}")
            buttons=[b for b in app.button
                     if "Generate interactive 3D crossing" in b.label]
            self.assertEqual(len(buttons),1,
                             "Results must offer a user-clickable 3D simulation")
            buttons[0].click().run(timeout=60)
            self.assertFalse(app.exception,
                f"3D concept fails after clicking result action: {app.exception}")
            titles=[item.body for item in app.markdown]
            self.assertTrue(any("Events worth reviewing" in x for x in titles))
            self.assertTrue(any("3D road intervention" in x for x in titles))


if __name__=="__main__":unittest.main()
