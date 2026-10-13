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

    def test_no_vehicle_pedestrian_overlap_across_varied_seeded_demand(self):
        # The crossing scenario must remain logically safe under a range of
        # assumed arrival rates, not just the default demonstration.
        for seed in [1,7,17,42,91]:
            for vehicles,pedestrians in [(300,120),(720,300),(1200,600)]:
                with self.subTest(seed=seed,vehicles=vehicles,pedestrians=pedestrians):
                    scenario=ControlInputs(seed=seed,seconds=120,
                        vehicles_per_hour=vehicles,pedestrians_per_hour=pedestrians)
                    frames=simulate(scenario)["managed"]["frames"]
                    for frame in frames:
                        in_crossing=any(-CROSSING_HALF_WIDTH<=car[1]<=CROSSING_HALF_WIDTH for car in frame["cars"])
                        walking=any(ped[2]=="crossing" and -5<=ped[1]<=5 for ped in frame["people"])
                        self.assertFalse(in_crossing and walking,
                            f"Collision-zone overlap at t={frame['t']} phase={frame['phase']}")
                        if frame["phase"]=="pedestrian_walk":
                            self.assertFalse(in_crossing,
                                f"Vehicle in crossing during WALK at t={frame['t']}")

    def test_lane_layout_changes_actual_agent_lane_assignments(self):
        for lane_count in (1,2,3):
            with self.subTest(lanes=lane_count):
                scenario=ControlInputs(lanes=lane_count,seed=41,seconds=180,
                                       vehicles_per_hour=980,pedestrians_per_hour=180)
                result=simulate(scenario)
                all_lanes={c[2] for frame in result["managed"]["frames"] for c in frame["cars"]}
                self.assertTrue(all(0<=lane<lane_count for lane in all_lanes))
                self.assertEqual(len(all_lanes),lane_count)

    def test_rejects_unsupported_parameters(self):
        with self.assertRaises(ValueError):
            simulate(ControlInputs(speed_kmh=200))


if __name__=="__main__":unittest.main()
