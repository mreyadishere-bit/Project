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

    def test_crossing_same_class_traffic_uses_motion_global_association(self):
        tracker=RoadTracker(max_age=4)
        records=[]
        for t in range(9):
            a_x=62+20*t
            # Avoid an information-theoretically unidentifiable frame in
            # which both same-class boxes have *exactly* identical coordinates.
            b_x=307-20*t
            detections=[
                {"bounds":(a_x,140,a_x+42,178),"cls":"car","confidence":.91},
                {"bounds":(b_x,140,b_x+42,178),"cls":"car","confidence":.92}
            ]
            if t%2:
                detections.reverse()  # detector output order is not identity
            observed=tracker.update(detections,(480,640,3))
            observed.sort(key=lambda d:d["bounds"][0])
            # Each physical car must retain its ID despite sorted positions.
            ids={int(d["bounds"][0]):d["track_id"] for d in observed}
            records.append((ids[a_x],ids[b_x]))
        self.assertEqual(len({pair[0] for pair in records}),1)
        self.assertEqual(len({pair[1] for pair in records}),1)
        self.assertNotEqual(records[0][0],records[0][1])
        self.assertIn(tracker.last_association,("global_lap","greedy_fallback"))

    def test_tracker_preserves_every_detected_box_even_without_match(self):
        tracker=RoadTracker()
        first=tracker.update([{"bounds":(20,10,60,48),"cls":"car","confidence":.9}],
                             (100,100,3))
        second=tracker.update([
          {"bounds":(22,10,62,48),"cls":"car","confidence":.9},
          {"bounds":(84,12,90,30),"cls":"person","confidence":.2}
        ],(100,100,3))
        self.assertEqual(len(second),2)
        self.assertEqual(first[0]["track_id"],second[0]["track_id"])
        self.assertNotEqual(second[0]["track_id"],second[1]["track_id"])

    def test_budgeted_detail_detection_recovers_missing_distant_car(self):
        import numpy as np
        frame=np.zeros((480,800,3),dtype="uint8")
        class ZoomModel(Model):
            def __init__(self):
                super().__init__()
                self.calls=0
            def predict(self,image,**kwargs):
                self.calls+=1
                # Full frame missed the tiny car. The cropped tile finds it.
                xy=[] if image.shape[1]==800 else [[75,65,112,105]]
                return [type("Result",(),{"boxes":Boxes(xy),"names":self.names})()]
        model=ZoomModel()
        found,_,raw=model_detections(
            model,frame,image_size=960,confidence=.12,class_ids=[2],
            device="cpu",tracker=RoadTracker(),detail_pass=True,detail_side=1)
        self.assertTrue(raw)
        self.assertEqual(model.calls,2)
        self.assertEqual(len(found),1)
        # Right tile begins at x=0.32*800 pixels.
        self.assertAlmostEqual(found[0]["bounds"][0],.32*800+75)
        self.assertEqual(found[0]["cls"],"car")
        self.assertGreater(found[0]["track_id"],0)

    def test_detail_nms_keeps_original_and_removes_repeated_crop_box(self):
        import numpy as np
        frame=np.zeros((480,800,3),dtype="uint8")
        class DuplicateModel(Model):
            def predict(self,image,**kwargs):
                if image.shape[1]==800:
                    coords=[[75,65,112,105]]
                else:
                    coords=[[75,65,112,105]]
                return [type("Result",(),{"boxes":Boxes(coords),"names":self.names})()]
        found,_,_=model_detections(
            DuplicateModel(),frame,image_size=960,confidence=.12,
            class_ids=[2],device="cpu",tracker=RoadTracker(),
            detail_pass=True,detail_side=0)
        self.assertEqual(len(found),1)

    def test_failed_detail_pass_keeps_full_frame_detections(self):
        import numpy as np
        frame=np.zeros((480,800,3),dtype="uint8")
        class FaultyDetailModel(Model):
            def predict(self,image,**kwargs):
                if image.shape[1]<800:
                    raise RuntimeError("Extra detail backend out of memory")
                return [type("Result",(),{
                    "boxes":Boxes([[110,200,165,250]]),"names":self.names
                })()]
        tracker=RoadTracker()
        found,_,_=model_detections(
            FaultyDetailModel(),frame,image_size=960,confidence=.12,
            class_ids=[2],device="cpu",tracker=tracker,
            detail_pass=True)
        self.assertEqual(len(found),1)
        self.assertEqual(found[0]["bounds"],(110.,200.,165.,250.))
        self.assertEqual(tracker.last_detail_added,0)
        self.assertTrue(tracker.last_detail_attempt)

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
