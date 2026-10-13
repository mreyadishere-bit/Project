"""Illustrative traffic scenario tests: deterministic, honest, tradeoffs."""
import unittest
from simulation_engine import Scenario, run_simulation


class SimulationTests(unittest.TestCase):
    def test_same_assumptions_have_same_outputs(self):
        scenario=Scenario()
        self.assertEqual(run_simulation(scenario),run_simulation(scenario))

    def test_no_measures_means_identical_before_after(self):
        result=run_simulation(Scenario(crossing=False,speed_calming=False))
        self.assertEqual(result["before"],result["after"])

    def test_speed_calming_increases_segment_travel_time(self):
        result=run_simulation(Scenario(crossing=False,speed_calming=True,
                                       approach_speed_kmh=50,target_speed_kmh=25))
        self.assertGreater(result["after"]["road_segment_travel_time_s"],
                           result["before"]["road_segment_travel_time_s"])
        self.assertEqual(result["after"]["vehicle_speed_kmh_assumed"],25)

    def test_crossing_can_reduce_temporal_exposure_but_increase_wait(self):
        r=run_simulation(Scenario(cars_per_hour=1000,pedestrians_per_hour=360,
                                  crossing=True,speed_calming=False))
        self.assertGreaterEqual(r["before"]["modeled_interaction_windows"],
                                r["after"]["modeled_interaction_windows"])
        self.assertGreaterEqual(r["after"]["mean_pedestrian_wait_s"],0)
        self.assertIn("NOT",r["methodology"])

    def test_invalid_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            run_simulation(Scenario(approach_speed_kmh=1))


if __name__=="__main__":
    unittest.main()
