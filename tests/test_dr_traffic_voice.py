"""No-model regression tests for Dr Traffic's optional spoken command mapping."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dr_traffic_voice import classify_voice_intent


class VoiceIntentTests(unittest.TestCase):
    def test_capture_photo(self):
        self.assertEqual(classify_voice_intent("تيك فوتو"), "capture_evidence_request")
        self.assertEqual(classify_voice_intent("take photo"), "capture_evidence_request")

    def test_signal_and_litter(self):
        self.assertEqual(classify_voice_intent("في عربية قطعت إشارة"), "traffic_signal_review_request")
        self.assertEqual(classify_voice_intent("رمي زبالة"), "litter_review_request")

    def test_unknown_is_just_a_note(self):
        self.assertEqual(classify_voice_intent("السلام عليكم"), "general_voice_note")


if __name__ == "__main__":
    unittest.main()
