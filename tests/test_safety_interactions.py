"""Evidence extracted from tracked frames should be time-indexed, conservative."""
import csv
from pathlib import Path
import tempfile
import unittest
from safety_interactions import find_interactions

FIELDS=["frame_number","video_second","track_id","class","confidence",
        "x1","y1","x2","y2","center_x","center_y"]

def row(frame,sec,ident,cls,x,y,confidence=.92):
    return dict(frame_number=frame,video_second=sec,track_id=ident,class_name=cls,
                **{"class":cls},confidence=confidence,x1=x-12,y1=y-28,
                x2=x+12,y2=y,center_x=x,center_y=y-14)

class InteractionReviewTests(unittest.TestCase):
    def write(self,folder,rows):
        path=Path(folder)/"objects.csv"
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction="ignore")
            w.writeheader()
            for r in rows:w.writerow(r)
        return path

    def test_repeated_time_localized_proximity_creates_review_not_collision(self):
        with tempfile.TemporaryDirectory() as temp:
            rows=[]
            for i in range(6):
                rows.extend([row(i,i*.4,"P1","person",400+i,300),
                             row(i,i*.4,"V7","car",415+i,305)])
            path=self.write(temp,rows)
            events=find_interactions(path,800,600)
            self.assertEqual(len(events),1)
            item=events[0]
            self.assertEqual(item["frame_count"],6)
            self.assertEqual(item["person_track"],"P1")
            self.assertIn("NOT a verified conflict",item["explanation"])
            self.assertAlmostEqual(item["end_second"],2.0)
            self.assertGreaterEqual(item["minimum_image_distance"],0)

    def test_single_nearby_frame_cannot_create_safety_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self.write(temp,[row(0,0,"P1","person",300,260),
                                 row(0,0,"V1","car",310,270)])
            self.assertEqual(find_interactions(path,800,600),[])

    def test_far_separated_road_users_not_flagged(self):
        with tempfile.TemporaryDirectory() as temp:
            rows=[]
            for i in range(6):
                rows.extend([row(i,i*.4,"P1","person",100,200),
                             row(i,i*.4,"V1","car",700,450)])
            self.assertEqual(find_interactions(self.write(temp,rows),800,600),[])

    def test_missing_calibration_or_file_returns_empty_not_an_invented_event(self):
        self.assertEqual(find_interactions("/missing.csv",1920,1080),[])
        with tempfile.TemporaryDirectory() as temp:
            file=self.write(temp,[row(1,1,"P1","person",120,150)])
            self.assertEqual(find_interactions(file,0,1080),[])


if __name__=="__main__":unittest.main()
