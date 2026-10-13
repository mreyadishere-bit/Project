"""Transparent, deterministic before/after traffic scenario explorer.

NOT a calibrated microscopic traffic model, prediction of injury reduction,
or 3D reconstruction of the uploaded road. Shared arrival sequences make
counterfactual comparisons meaningful as illustrations only.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Scenario:
    approach_speed_kmh: int = 45
    cars_per_hour: int = 650
    pedestrians_per_hour: int = 180
    crossing: bool = True
    speed_calming: bool = True
    target_speed_kmh: int = 28
    seed: int = 2026
    duration_seconds: int = 300


def _arrivals(rate_per_hour, duration, rng):
    rate = rate_per_hour / 3600
    arrivals = []
    if rate <= 0:
        return arrivals
    t = 0.
    while t < duration:
        t += rng.expovariate(rate)
        if t < duration:
            arrivals.append(round(t, 2))
    return arrivals


def _model(cars, pedestrians, speed_kmh: float, crossing: bool, duration: int):
    mps = speed_kmh / 3.6
    # Simplified straight 100m road, 50m to imaginary crossing.
    arrival_at_crossing = [t + 50/mps for t in cars]
    vehicle_times = sorted(arrival_at_crossing)
    pedestrian_crossings = []
    waiting_times = []
    exposure = 0
    for arrival in pedestrians:
        crossing_start = arrival
        crossing_duration = 8.0  # chosen simplified width/walking speed assumption
        if crossing:
            # Pedestrians wait for a modeled temporal gap; this is NOT an
            # actual crosswalk safety controller or signal phasing design.
            for _ in range(80):
                lo = bisect_left(vehicle_times, crossing_start - 2.0)
                nearest = vehicle_times[lo:lo+30]
                conflict = [t for t in nearest if crossing_start-2 <= t <= crossing_start+crossing_duration+2]
                if not conflict:
                    break
                crossing_start = max(conflict) + 2.1
                if crossing_start > arrival + 120:
                    break
        waiting_times.append(max(0., crossing_start - arrival))
        pedestrian_crossings.append((round(crossing_start,2), round(crossing_start+crossing_duration,2)))
        start = crossing_start - 1.5
        end = crossing_start + crossing_duration + 1.5
        k = bisect_left(vehicle_times, start)
        exposure += sum(start <= t <= end for t in vehicle_times[k:k+45])
    return {
        "car_count": len(cars),
        "pedestrian_count": len(pedestrians),
        "modeled_interaction_windows": exposure,
        "mean_pedestrian_wait_s": round(sum(waiting_times)/len(waiting_times), 1) if waiting_times else 0.,
        "vehicle_speed_kmh_assumed": round(speed_kmh,1),
        "road_segment_travel_time_s": round(100/mps,1),
        "pedestrian_crossings": pedestrian_crossings[:100],
        "vehicle_entries": cars[:180],
    }


def run_simulation(scenario: Scenario):
    if not (10 <= scenario.approach_speed_kmh <= 100 and 10 <= scenario.target_speed_kmh <= 100):
        raise ValueError("Speeds must be between 10 and 100 km/h.")
    if not (0 <= scenario.cars_per_hour <= 2400 and 0 <= scenario.pedestrians_per_hour <= 1500):
        raise ValueError("Scenario flow is outside supported range.")
    if not 60 <= scenario.duration_seconds <= 900:
        raise ValueError("Simulation duration is outside supported range.")
    cars = _arrivals(scenario.cars_per_hour, scenario.duration_seconds,
                     random.Random(scenario.seed))
    walkers = _arrivals(scenario.pedestrians_per_hour, scenario.duration_seconds,
                        random.Random(scenario.seed + 1))
    baseline = _model(cars, walkers, scenario.approach_speed_kmh, False, scenario.duration_seconds)
    improved_speed = (min(scenario.approach_speed_kmh, scenario.target_speed_kmh)
                      if scenario.speed_calming else scenario.approach_speed_kmh)
    improved = _model(cars, walkers, improved_speed, scenario.crossing, scenario.duration_seconds)
    return {
        "before": baseline, "after": improved,
        "parameters": {
            "approach_speed_kmh": scenario.approach_speed_kmh,
            "target_speed_kmh": scenario.target_speed_kmh,
            "cars_per_hour": scenario.cars_per_hour,
            "pedestrians_per_hour": scenario.pedestrians_per_hour,
            "crossing": scenario.crossing,
            "speed_calming": scenario.speed_calming,
            "duration_seconds": scenario.duration_seconds,
            "seed": scenario.seed,
        },
        "methodology": (
            "Deterministic toy model: a single straight 100 m road, independent "
            "randomized car/pedestrian arrival times, fixed walking duration, "
            "cars traveling at assumed constant speeds and optional pedestrian "
            "gap-waiting logic. Interaction windows are temporal overlaps, NOT "
            "collisions, near misses or empirically predicted crashes. "
            "No calibration to the video or real roadway has been performed."
        ),
    }
