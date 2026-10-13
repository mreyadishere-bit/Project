"""No hallucinated accuracy: hand-labeled frame matching tests."""
import csv
import tempfile
import unittest
from pathlib import Path
from detection_qa import evaluate_detections


class DetectionQATests(unittest.TestCase):
    def output(self,folder,rows):
        file=Path(folder)/"objects.csv"
        fields=["frame_number","class","x1","y1","x2","y2","confidence"]
        with file.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            w.writerows(rows)
        return file

    def test_only_hand_labeled_frames_contribute_to_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            predicted=self.output(tmp,[
                dict(frame_number=1,**{"class":"car"},x1=1,y1=1,x2=11,y2=11,confidence=.9),
                dict(frame_number=2,**{"class":"car"},x1=1,y1=1,x2=11,y2=11,confidence=.9),
                dict(frame_number=3,**{"class":"person"},x1=15,y1=15,x2=30,y2=30,confidence=.8),
            ])
            gt="frame_number,class,x1,y1,x2,y2\n1,car,1,1,11,11\n2,none,0,0,0,0\n"
            qa=evaluate_detections(gt,predicted)
            self.assertEqual(qa["annotated_frames"],2)
            self.assertEqual(qa["overall"]["tp"],1)
            self.assertEqual(qa["overall"]["fp"],1)
            self.assertEqual(qa["overall"]["fn"],0)
            self.assertEqual(qa["overall"]["precision"],.5)
            self.assertEqual(qa["overall"]["recall"],1.0)
            self.assertNotIn("person",qa["classes"])

    def test_misses_and_false_positives_count_per_class(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred=self.output(tmp,[dict(frame_number=8,**{"class":"truck"},x1=30,y1=30,x2=40,y2=40,confidence=.99)])
            truth="frame_number,class,x1,y1,x2,y2\n8,car,0,0,10,10\n"
            qa=evaluate_detections(truth,pred)
            self.assertEqual(qa["overall"]["tp"],0)
            self.assertEqual(qa["overall"]["fp"],1)
            self.assertEqual(qa["overall"]["fn"],1)
            self.assertEqual(qa["overall"]["f1"],0)

    def test_without_ground_truth_never_reports_accuracy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred=self.output(tmp,[])
            with self.assertRaisesRegex(ValueError,"No annotated frames"):
                evaluate_detections("frame_number,class,x1,y1,x2,y2\n",pred)

    def test_iou_matching_rejects_misaligned_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred=self.output(tmp,[dict(frame_number=1,**{"class":"car"},x1=10,y1=10,x2=20,y2=20,confidence=.9)])
            truth="frame_number,class,x1,y1,x2,y2\n1,car,50,50,60,60\n"
            qa=evaluate_detections(truth,pred)
            self.assertEqual(qa["overall"]["tp"],0)
            self.assertEqual(qa["overall"]["fn"],1)


if __name__=="__main__":unittest.main()
