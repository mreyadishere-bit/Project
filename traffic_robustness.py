"""Sensitivity analysis of conceptual traffic interventions across independent demand seeds.

These are NOT statistical estimates of actual road safety benefit.
Run a set of paired baseline/managed simulations, matched within each seed.
"""
from __future__ import annotations
from dataclasses import replace
from statistics import median
from traffic_control_sim import ControlInputs, simulate

OUTPUTS = (
    "mean_pedestrian_wait_s",
    "mean_vehicle_travel_s",
    "max_waiting_vehicles",
    "vehicles_completed",
    "pedestrians_completed",
    "vehicle_stopped_seconds",
)


def assess_robustness(inputs: ControlInputs, runs: int = 5) -> dict:
    if runs < 3 or runs > 15:
        raise ValueError("Choose between 3 and 15 reproducible trials.")
    records = []
    for i in range(runs):
        sample = replace(inputs, seed=inputs.seed+7919*i)
        model = simulate(sample)
        base = model["baseline"]["metrics"]
        after = model["managed"]["metrics"]
        records.append({
            "trial": i + 1,
            "seed": sample.seed,
            "baseline": {k:base.get(k) for k in OUTPUTS},
            "managed": {k:after.get(k) for k in OUTPUTS},
        })
    metrics = {}
    for key in OUTPUTS:
        pairs = [(r["baseline"].get(key),r["managed"].get(key)) for r in records]
        pairs = [(a,b) for a,b in pairs if isinstance(a,(float,int)) and isinstance(b,(float,int))]
        if not pairs:
            metrics[key] = {"n":0, "baseline_median":None,"managed_median":None,
                            "paired_change_median":None,"paired_changes_range":None}
            continue
        changes=[b-a for a,b in pairs]
        metrics[key]={
            "n":len(pairs),
            "baseline_median":round(median(a for a,_ in pairs),2),
            "managed_median":round(median(b for _,b in pairs),2),
            "paired_change_median":round(median(changes),2),
            "paired_changes_range":[round(min(changes),2),round(max(changes),2)],
        }
    return {
        "runs":runs,
        "method":"Paired, independently seeded arrival demand with the same modeled demand under both traffic-control policies per seed.",
        "disclaimer":"Simulation sensitivity only. These are not measured confidence intervals, injury-risk reduction, road design certification, or forecasts for the uploaded footage.",
        "metrics":metrics,
        "trials":records,
    }
