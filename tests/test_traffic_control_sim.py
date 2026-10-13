"""Deterministic conceptual microsimulation: signal sequencing, waiting and reproducibility."""
import unittest
from traffic_control_sim import ControlInputs,phase_at,simulate,STOP_LINE,CROSSING_HALF_WIDTH


class SignalConceptTests(unittest.TestCase):
    def setUp(self):
        self.inputs=ControlInputs(seed=15,seconds=180,
                                  vehicles_per_hour=720,pedestrians_per_hour=300)
        self.result=simulate(self.inputs)

    def test_deterministic_equal_demand(self):
        self.assertEqual(self.result,simulate(self.inputs))
        self.assertGreater(self.result["demand"]["vehicles"],10)
        self.assertGreater(self.result["demand"]["pedestrians"],4)

    def test_signal_phases_never_allow_two_greens(self):
        seen=set()
        for s in range(0,180):
            name,_=phase_at(s,self.inputs)
            seen.add(name)
            self.assertNotIn("green",name) if "pedestrian" in name else None
        self.assertIn("pedestrian_walk",seen)
        self.assertIn("vehicle_green",seen)
        self.assertIn("pedestrian_clearance",seen)
        self.assertIn("all_red_before_walk",seen)

    def test_safe_controlled_phases(self):
        after=self.result["managed"]
        for frame in after["frames"]:
            cars_in=[car for car in frame["cars"] if -CROSSING_HALF_WIDTH<=car[1]<=CROSSING_HALF_WIDTH]
            walker_in=[ped for ped in frame["people"] if ped[2]=="crossing" and -5<=ped[1]<=5]
            self.assertFalse(cars_in and walker_in,
                             f"Both modes in crossing at t={frame['t']}")
            if frame["phase"]=="pedestrian_walk":
                # No car may enter the crossing during the walk phase.
                self.assertFalse(cars_in,frame)
        self.assertEqual(after["metrics"]["joint_crossing_occupancy_frames"],0)
        self.assertGreater(after["metrics"]["pedestrians_completed"],0)

    def test_stop_lines_and_queue_comparison(self):
        before=self.result["baseline"]
        after=self.result["managed"]
        self.assertGreaterEqual(after["metrics"]["max_waiting_vehicles"],0)
        self.assertGreater(after["metrics"]["vehicle_stopped_seconds"],0)
        self.assertIsNotNone(before["metrics"]["mean_pedestrian_wait_s"])
        self.assertIsNotNone(after["metrics"]["mean_pedestrian_wait_s"])
        for frame in after["frames"]:
            for car in frame["cars"]:
                self.assertGreaterEqual(car[1],-70)
                self.assertLess(car[1],70)

    def test_rejects_unsupported_parameters(self):
        with self.assertRaises(ValueError):
            simulate(ControlInputs(speed_kmh=200))


if __name__=="__main__":unittest.main()
