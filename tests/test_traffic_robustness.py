import unittest
from traffic_control_sim import ControlInputs
from traffic_robustness import assess_robustness

class RobustnessSimulationTests(unittest.TestCase):
    def test_paired_trials_reproducible_with_multiple_seeds(self):
        settings=ControlInputs(seconds=90,seed=33,vehicles_per_hour=450,pedestrians_per_hour=160)
        a=assess_robustness(settings,runs=5)
        b=assess_robustness(settings,runs=5)
        self.assertEqual(a,b)
        self.assertEqual(a["runs"],5)
        self.assertEqual(len({x["seed"] for x in a["trials"]}),5)

    def test_reported_change_is_derived_from_per_trial_pairs(self):
        report=assess_robustness(ControlInputs(seconds=90,seed=41),runs=3)
        result=report["metrics"]["max_waiting_vehicles"]
        differences=[x["managed"]["max_waiting_vehicles"]-
                     x["baseline"]["max_waiting_vehicles"] for x in report["trials"]]
        self.assertEqual(result["paired_changes_range"],[min(differences),max(differences)])
        self.assertEqual(result["n"],3)

    def test_invalid_runs_rejected(self):
        with self.assertRaises(ValueError):
            assess_robustness(ControlInputs(),runs=1)

if __name__=="__main__":unittest.main()
