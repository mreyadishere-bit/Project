import unittest
from calibrated_conflicts import ground_interaction_candidates

class CalibratedConflictTests(unittest.TestCase):
    def samples(self,y):
        return [(float(t)/2,4+0*float(t),y) for t in range(8)]

    def test_repeated_convergent_world_tracks_become_review_only(self):
        track={"tracks":[
            {"track_id":1,"class":"person","points":[(t*.5,6.,0.) for t in range(8)]},
            {"track_id":2,"class":"car","points":[(t*.5,t*1.0,0.) for t in range(8)]},
        ]}
        events=ground_interaction_candidates(track)
        self.assertGreater(len(events),0)
        self.assertGreaterEqual(events[0]["supporting_time_bins"],2)
        self.assertIn("not validated TTC",events[0]["interpretation"])
        self.assertLessEqual(events[0]["model_closest_point_distance_m"],2.5)

    def test_distant_tracks_do_not_create_interaction(self):
        data={"tracks":[
            {"track_id":1,"class":"person","points":[(t*.5,6.,20.) for t in range(8)]},
            {"track_id":2,"class":"car","points":[(t*.5,t*1.,0.) for t in range(8)]}
        ]}
        self.assertEqual(ground_interaction_candidates(data),[])

    def test_no_calibrated_tracks_no_claim(self):
        self.assertEqual(ground_interaction_candidates({"tracks":[]}),[])

    def test_invalid_threshold_rejected(self):
        with self.assertRaises(ValueError):
            ground_interaction_candidates({"tracks":[]},horizon_s=90)

if __name__=="__main__":unittest.main()
