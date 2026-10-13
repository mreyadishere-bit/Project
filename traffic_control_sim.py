"""Deterministic, transparent, two-lane traffic-control *concept* simulator.

This is NOT an automatically calibrated video digital twin or crash predictor.
Same seeded demand drives unmanaged-gap and signal-managed scenarios.
Car following uses constrained accel/braking and minimum lane gaps.
Signal cycle explicitly includes yellow, all-red, WALK and clearance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
import random

DT = 0.25
ROAD_START = -70.
ROAD_END = 70.
STOP_LINE = -10.
CROSSING_HALF_WIDTH = 3.5
CROSSING_WALK_METRES = 14.
WALKING_MPS = 1.4
CAR_LENGTH = 4.7
FOLLOW_GAP = 3.


@dataclass(frozen=True)
class ControlInputs:
    speed_kmh: int = 36
    vehicles_per_hour: int = 600
    pedestrians_per_hour: int = 240
    green_s: int = 36
    walk_s: int = 16
    clearance_s: int = 12
    seconds: int = 180
    seed: int = 2026


def phases(settings: ControlInputs):
    """Returns (current phase, time remaining); vehicular and WALK never green simultaneously."""
    cycle = (
        ("vehicle_green", settings.green_s),
        ("vehicle_yellow", 4),
        ("all_red_before_walk", 3),
        ("pedestrian_walk", settings.walk_s),
        ("pedestrian_clearance", settings.clearance_s),
        ("all_red_before_green", 3),
    )
    return cycle


def phase_at(time, settings: ControlInputs):
    offset = time % sum(duration for _, duration in phases(settings))
    for name, length in phases(settings):
        if offset < length-1e-9:
            return name, round(length-offset, 2)
        offset -= length
    return phases(settings)[-1][0], 0


def _arrivals(rate, seconds, rng, first=0):
    if rate <= 0:
        return []
    t = float(first)
    result = []
    while t < seconds:
        t += rng.expovariate(rate/3600.)
        if t < seconds:
            result.append(round(t, 3))
    return result


def _demand(settings):
    car_times = _arrivals(settings.vehicles_per_hour, settings.seconds,
                          random.Random(settings.seed), first=-3.0)
    ped_times = _arrivals(settings.pedestrians_per_hour, settings.seconds,
                          random.Random(settings.seed + 17), first=-3.0)
    rng = random.Random(settings.seed + 31)
    return [(i,t,rng.randrange(2)) for i,t in enumerate(car_times)], [
        (i,t) for i,t in enumerate(ped_times)]


def _simulate(settings, car_demand, ped_demand, *, controlled):
    speed = settings.speed_kmh/3.6
    car_index = ped_index = 0
    cars, walkers = [], []
    finished_vehicle_times = []
    finished_ped_waits = []
    total_vehicle_stop_seconds = 0.
    queue_peak = 0
    simultaneous_crossing_frames = 0
    yield_checks = 0
    snapshots = []
    frame_stride = 2  # store 0.5-second views, still simulate with 0.25 s DT
    steps = round(settings.seconds/DT)
    for step in range(steps + 1):
        now = step*DT
        phase, remaining = (phase_at(now,settings) if controlled
                            else ("uncontrolled",0))
        while car_index < len(car_demand) and car_demand[car_index][1] <= now:
            ident, arrival, lane = car_demand[car_index]
            car_index += 1
            # Spawn independently by lane; if queue extends to entrance,
            # buffer entry rather than spawning overlapping vehicles.
            existing = [c["x"] for c in cars if c["lane"]==lane]
            if existing and min(existing) < ROAD_START+CAR_LENGTH+FOLLOW_GAP:
                # Let the waiting vehicle appear later, keeping its arrival time.
                car_index -= 1
                break
            cars.append({"id":ident, "arrival":arrival, "lane":lane,
                         "x":ROAD_START, "v":speed, "stopped":0.})
        while ped_index < len(ped_demand) and ped_demand[ped_index][1] <= now:
            ident, arrival = ped_demand[ped_index]
            ped_index+=1
            walkers.append({"id":ident,"arrival":arrival,
                            "status":"waiting","y":-7., "start":None})
        crossing_people = any(p["status"]=="crossing" for p in walkers)
        near_cars = any(-38 <= c["x"] <= 14 for c in cars)
        for p in walkers:
            if p["status"]=="waiting":
                permitted = (phase=="pedestrian_walk" if controlled
                             else not near_cars and not crossing_people)
                if permitted:
                    p["status"]="crossing"
                    p["start"]=now
                    crossing_people=True
                    if not controlled:
                        yield_checks+=1
            if p["status"]=="crossing":
                p["y"]=min(7., -7. + (now-p["start"])*WALKING_MPS)
                if p["y"]>=7-1e-6:
                    p["status"]="finished"
                    finished_ped_waits.append(p["start"]-p["arrival"])
        crossing_people = any(p["status"]=="crossing" for p in walkers)
        new_cars = []
        for lane in (0,1):
            leaders = sorted((c for c in cars if c["lane"]==lane),
                             key=lambda c:-c["x"])
            lead = None
            for car in leaders:
                previous_v=car["v"]
                gap_distance = float("inf") if lead is None else (lead["x"]-car["x"]-CAR_LENGTH-FOLLOW_GAP)
                stop_needed = (controlled and phase!="vehicle_green"
                               or not controlled and crossing_people)
                if stop_needed and car["x"] < STOP_LINE:
                    dist=STOP_LINE-car["x"]-.5
                    allowed=sqrt(max(0.,2*3.*max(0.,dist)))
                else:
                    allowed=speed
                if gap_distance<float("inf"):
                    # Braking curve prevents acceleration through predecessor.
                    allowed=min(allowed, sqrt(max(0.,2*3.*max(0.,gap_distance))))
                target=min(speed,allowed)
                # Conservative kinematic acceleration envelope.
                v=min(previous_v+1.7*DT,target)
                v=max(previous_v-3.0*DT,v,0.)
                if allowed<previous_v:
                    v=max(0.,min(v,allowed))
                delta=max(0.,v*DT)
                if lead is not None:
                    delta=min(delta,max(0.,lead["x"]-CAR_LENGTH-FOLLOW_GAP-car["x"]))
                if stop_needed and car["x"]<STOP_LINE:
                    delta=min(delta,max(0.,STOP_LINE-.5-car["x"]))
                car["x"]+=delta
                car["v"]=delta/DT if step>0 else v
                if car["v"]<.7:
                    car["stopped"]+=DT
                    total_vehicle_stop_seconds+=DT
                if car["x"]>=ROAD_END:
                    finished_vehicle_times.append(now-car["arrival"])
                else:
                    new_cars.append(car)
                lead = car
        cars = new_cars
        waiting_queue=sum(1 for car in cars if -40<=car["x"]<=STOP_LINE
                          and car["v"]<2)
        queue_peak=max(queue_peak,waiting_queue)
        vehicle_in_crossing=any(-CROSSING_HALF_WIDTH <= c["x"] <= CROSSING_HALF_WIDTH for c in cars)
        person_in_crossing=any(p["status"]=="crossing" and -5<=p["y"]<=5 for p in walkers)
        if vehicle_in_crossing and person_in_crossing:
            simultaneous_crossing_frames+=1
        if step%frame_stride==0:
            snapshots.append({
                "t":round(now,2),
                "phase":phase,
                "phase_remaining_s":remaining,
                "cars":[[c["id"],round(c["x"],2),c["lane"],round(c["v"],2)] for c in cars],
                "people":[[p["id"],round(p["y"],2),p["status"]] for p in walkers
                          if p["status"]!="finished"],
            })
        walkers=[p for p in walkers if p["status"]!="finished"]
    return {
        "frames":snapshots,
        "metrics":{
            "vehicles_completed":len(finished_vehicle_times),
            "pedestrians_completed":len(finished_ped_waits),
            "mean_vehicle_travel_s":round(sum(finished_vehicle_times)/len(finished_vehicle_times),1) if finished_vehicle_times else None,
            "mean_pedestrian_wait_s":round(sum(finished_ped_waits)/len(finished_ped_waits),1) if finished_ped_waits else None,
            "max_waiting_vehicles":queue_peak,
            "vehicle_stopped_seconds":round(total_vehicle_stop_seconds,1),
            "joint_crossing_occupancy_frames":simultaneous_crossing_frames,
            "crossing_review_events":yield_checks,
        }
    }


def simulate(inputs: ControlInputs = ControlInputs()):
    if not (10<=inputs.speed_kmh<=70
            and 0<=inputs.vehicles_per_hour<=1200
            and 0<=inputs.pedestrians_per_hour<=600
            and 20<=inputs.green_s<=70
            and 12<=inputs.walk_s<=30
            and 10<=inputs.clearance_s<=30
            and 60<=inputs.seconds<=300):
        raise ValueError("Scenario parameters out of tested range")
    cars,peds=_demand(inputs)
    before=_simulate(inputs,cars,peds,controlled=False)
    after=_simulate(inputs,cars,peds,controlled=True)
    return {
        "inputs":asdict(inputs),
        "demand":{"vehicles":len(cars),"pedestrians":len(peds)},
        "baseline":before,
        "managed":after,
        "methodology":"Illustrative deterministic, two-lane one-directional road; "
                      "fixed geometry of 140 m and a 14 m pedestrian traversal; "
                      "seeded independent demand; simplified car-following and stop-line controller. "
                      "Not fitted to footage, not an approved signal timing plan, "
                      "not a crash/near-miss prediction. No measured safety percentage.",
    }
