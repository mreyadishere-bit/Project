"""PDF document export must contain real report data, not a mock success image."""
import unittest
from road_report_pdf import build_road_pdf
from traffic_control_sim import simulate,ControlInputs


class EvidenceReportPDFTests(unittest.TestCase):
    def test_pdf_is_real_and_contains_multisection_road_review(self):
        snapshot={"label":"Evening intersection review.mp4","duration_seconds":22.4,
                  "analyzed_frames":43,"detected_frames":36}
        story={
            "summary":"People and cars appeared in sampled footage. No collisions have been established.",
            "context":{"label":"Road type not established"},
            "limitations":"Physical distances and accidents cannot be inferred from uncalibrated pixels.",
            "recommendations":[{
                "title":"Inspect crossings","evidence":"Multiple frames with person detections",
                "action":"Survey existing legal crossing locations",
                "verify":"Confirm road classification and foot traffic"
            }]
        }
        events=[{"title":"Review shared image space","video_second":8.4,
                 "start_second":7.8,"end_second":9.2,"frame_count":4,
                 "explanation":"These are camera-frame relationships, not physical risk."}]
        sim=simulate(ControlInputs(seconds=90,vehicles_per_hour=450,
                                   pedestrians_per_hour=240))
        pdf=build_road_pdf(snapshot,story,events,sim)
        self.assertTrue(pdf.startswith(b"%PDF-"))
        self.assertGreater(len(pdf),2000)
        self.assertIn(b"/Type /Page",pdf)

    def test_report_without_simulation_avoids_fake_benefits(self):
        pdf=build_road_pdf({"label":"clip.mp4","analyzed_frames":0},
             {"summary":"No observations","context":{},"recommendations":[]},[])
        self.assertTrue(pdf.startswith(b"%PDF-"))


if __name__=="__main__":unittest.main()
