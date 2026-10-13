"""CI regression tests for separating raw detector boxes from track association."""
import unittest
from road_tracking import RoadTracker, model_detections


class Tensor:
    def __init__(self, data):self.data=data
    def cpu(self):return self
    def int(self):return self
    def tolist(self):return self.data

class Boxes:
    def __init__(self, coords):
        self.xyxy=Tensor(coords)
        self.conf=Tensor([.68]*len(coords))
        self.cls=Tensor([2]*len(coords))
        self.id=None
    def __len__(self):return len(self.xyxy.data)

class Model:
    names={2:"car"}
    def __init__(self):self.coords=[]
    def predict(self, frame,**kwargs):
        return [type("Result",(),{"boxes":Boxes(self.coords),"names":self.names})()]

class TestRoadTracker(unittest.TestCase):
    def test_raw_detection_does_not_need_ultralytics_track_id(self):
        import numpy as np
        model=Model()
        tracker=RoadTracker()
        frame=np.zeros((360,640,3),dtype="uint8")
        model.coords=[[10,150,80,200],[300,120,380,190]]
        first,_,raw=model_detections(model,frame,image_size=640,confidence=.12,
                                  class_ids=[2],device="cpu",tracker=tracker)
        self.assertTrue(raw)
        self.assertEqual(len(first),2)
        self.assertEqual(len({d["track_id"] for d in first}),2)
        model.coords=[[16,154,86,204],[305,125,385,195]]
        second,_,_=model_detections(model,frame,image_size=640,confidence=.12,
                                   class_ids=[2],device="cpu",tracker=tracker)
        self.assertEqual([d["track_id"] for d in second],[d["track_id"] for d in first])

    def test_occasional_empty_detections_do_not_erase_future_matches(self):
        import numpy as np
        model=Model(); tracker=RoadTracker(max_age=5)
        frame=np.zeros((100,200,3),dtype="uint8")
        model.coords=[[35,20,85,70]]
        before,_,_=model_detections(model,frame,image_size=640,confidence=.12,
                                   class_ids=[2],device="cpu",tracker=tracker)
        model.coords=[]
        missing,_,_=model_detections(model,frame,image_size=640,confidence=.12,
                                    class_ids=[2],device="cpu",tracker=tracker)
        self.assertEqual(missing,[])
        model.coords=[[39,23,89,73]]
        after,_,_=model_detections(model,frame,image_size=640,confidence=.12,
                                  class_ids=[2],device="cpu",tracker=tracker)
        self.assertEqual(before[0]["track_id"],after[0]["track_id"])

if __name__ == "__main__":unittest.main()
