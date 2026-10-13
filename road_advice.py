"""Evidence-gated road engineering review suggestions for completed video.

This module does not classify a highway from uncalibrated speed, invent crash
reductions, or recommend a crossing based merely on box proximity.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import median


VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}


def context_from_source(source: str, evidence: dict) -> dict:
    """Conservative context prior, never a computer-vision classification."""
    words = Path(source).stem.lower().replace("_", " ").replace("-", " ")
    highway = any(w in words.split() for w in ("highway", "freeway", "motorway", "autobahn", "expressway"))
    label = "Possible highway / divided road" if highway else "Road type not established"
    return {
        "kind": "highway_hint" if highway else "unknown",
        "label": label,
        "basis": "The source file's title suggests a highway; not independently verified from pixels." if highway
                 else "No reliable road classification is available from this recording.",
        "pedestrian_infrastructure_claim_allowed": False,
    }


def trajectory_evidence(objects_file: Path | str | None, max_tracks=15000):
    """Bounded per-track metadata from true detections across the file."""
    if not objects_file or not Path(objects_file).is_file():
        return {"tracks": 0, "direction_changes": 0, "speed_samples": 0,
                "speed_kmh_median": None, "sample_coverage": "No tracked CSV evidence"}
    last = {}
    heading_change = set()
    speeds = []
    for row in csv.DictReader(Path(objects_file).open(encoding="utf-8-sig", newline="")):
        try:
            ident = row.get("track_id", "")
            if not ident or row.get("class") not in VEHICLE_CLASSES:
                continue
            key = (row["class"], ident)
            if key not in last and len(last) >= max_tracks:
                continue
            sec = float(row["video_second"])
            x = float(row["center_x"])
            y = float(row["center_y"])
            old = last.get(key)
            if old:
                a, b, t, baseline = old
                if 0 < sec - t <= 3 and abs(x-a)+abs(y-b) > 3:
                    # Image-plane motion angle varies under perspective even on a
                    # straight road. Flag for human visual review only.
                    dx, dy = x-a, y-b
                    import math
                    angle = math.atan2(dy,dx)
                    if baseline is not None:
                        change = abs((angle-baseline+math.pi)%(2*math.pi)-math.pi)
                        if change > .65:  # 37 degrees within an observed track
                            heading_change.add(key)
                    baseline = angle
                last[key] = (x,y,sec,baseline)
            else:
                last[key] = (x,y,sec,None)
            v = row.get("calibrated_speed_kmh","")
            if v:
                value = float(v)
                if 0 < value <= 160 and len(speeds) < 20000:
                    speeds.append(value)
        except (KeyError, ValueError, TypeError):
            continue
    return {
        "tracks": len(last),
        "direction_changes": len(heading_change),
        "speed_samples": len(speeds),
        "speed_kmh_median": round(median(speeds), 1) if speeds else None,
        "sample_coverage": "Time-sampled tracked objects; ID switches and occlusion are possible.",
    }


def _recommendation(identifier, title, evidence, why, action, verify,
                    proposed_change="inspection", priority="Review", benefit="Not measured"):
    return {
        "id": identifier, "title": title, "evidence": evidence, "reason": why,
        "action": action, "verify": verify, "priority": priority,
        "expected_benefit": benefit, "confidence": "Requires site verification",
        "simulation_option": proposed_change,
    }


def road_report(evidence: dict, source: str, objects_file=None) -> dict:
    frames = evidence.get("analyzed_frames",0)
    context = context_from_source(source,evidence)
    tracks = trajectory_evidence(objects_file)
    percentages = evidence.get("percent_of_sampled_frames", {})
    avgs = evidence.get("averages_per_frame", {})
    vehicles = percentages.get("vehicles",0)
    pedestrians = percentages.get("pedestrians",0)
    crowded = percentages.get("crowded_image",0)
    dark = percentages.get("dark_image",0)
    proximity = percentages.get("close_in_image",0)
    recs=[]
    if frames < 10 or vehicles < 8 or tracks["tracks"] < 3:
        recs.append(_recommendation(
            "collect_evidence", "Collect stronger traffic evidence",
            f"{frames} frames analyzed; vehicles appeared in {vehicles:.1f}% of sampled frames; {tracks['tracks']} vehicle tracks.",
            "This recording is not sufficient to justify a specific physical road intervention.",
            "Recheck detection coverage and inspect a longer, representative sample of traffic from this camera.",
            "Manually label sample frames and compare counted vehicles with the source video.",
            proposed_change="inspection",priority="Data quality"))
    else:
        if crowded >= 15 or avgs.get("vehicles",0) >= 6:
            recs.append(_recommendation(
                "flow", "Investigate traffic flow at the observed busy periods",
                f"High image occupancy in {crowded:.1f}% of sampled frames; average {avgs.get('vehicles',0):.1f} vehicles visible per sampled frame.",
                "Repeated concentrations of vehicles merit reviewing whether queuing or merging actually occurs.",
                "Review lane use, merge markings, and measured travel times before changing road geometry.",
                "Confirm actual queue length, demand, lane geometry, and time-of-day consistency.",
                proposed_change="markings",benefit="Clearer guidance might help; no benefit quantified."))
        if tracks["direction_changes"] >= 3:
            recs.append(_recommendation(
                "path", "Inspect lane guidance where tracked movement changes direction",
                f"{tracks['direction_changes']} tracks showed substantial turns in image-plane movement; some apparent turning can be caused by camera perspective.",
                "Recorded trajectories changed screen direction; this does not prove unsafe driving or lane changes.",
                "Inspect curve delineators, lane marking visibility and merging signs at the corresponding locations.",
                "Use site geometry and full-resolution video to verify whether vehicles truly changed lanes.",
                proposed_change="markings",benefit="Improved guidance is plausible but untested."))
        if dark >= 20:
            recs.append(_recommendation(
                "light", "Check road illumination and camera exposure",
                f"{dark:.1f}% of sampled frames were classified as low image brightness.",
                "The camera scene appeared dark, which could reflect exposure settings rather than road lighting.",
                "Measure roadway light levels and inspect retroreflective signs, after checking camera exposure.",
                "Survey light levels at night with calibrated instruments.",
                proposed_change="lighting",benefit="Could improve visibility if deficient lighting is confirmed."))
        if pedestrians >= 20 and proximity >= 10 and context["kind"] != "highway_hint":
            recs.append(_recommendation(
                "pedestrians", "Review how pedestrians and vehicles interact",
                f"Pedestrians visible in {pedestrians:.1f}% of frames; image-space proximity occurred in {proximity:.1f}%.",
                "Pedestrian–vehicle image overlap is not physical proximity or proof that a crossing is needed.",
                "Survey pedestrian desire lines and existing formal crossings before proposing changes.",
                "Confirm roadway class, crossing demand, speeds and physical separation on site.",
                proposed_change="inspection",benefit="No crosswalk automatically recommended."))
        # No speed-reduction proposal from pixels/s or generic vehicle class.
        if tracks["speed_samples"]:
            recs.append(_recommendation(
                "speed", "Validate measured approach speeds against posted limits",
                f"{tracks['speed_samples']} calibrated kinematic samples, median {tracks['speed_kmh_median']} km/h.",
                "World-plane velocity estimates exist but are not validated against a radar or surveyed checkpoints.",
                "Compare calibrated speed samples with field measurements and posted limits.",
                "Confirm camera calibration, measurement error and the legal posted speed.",
                proposed_change="speed_review",benefit="No proposed speed limit without survey."))
    if not recs:
        recs.append(_recommendation(
            "verify", "Complete a targeted road safety site review",
            f"{frames} analyzed frames, vehicle presence {vehicles:.1f}%; no experimental trigger exceeded review thresholds.",
            "No specific change is justified by the available video observations alone.",
            "Inspect road signs, roadside obstacles, pavement and geometry under different conditions.",
            "Use field measurements and longer-term incident/traffic data.",
            proposed_change="inspection",priority="Routine"))
    # No routine recommendation casually adds pedestrian crossings or changes limits.
    return {
        "context": context, "measurements": tracks,
        "recommendations": recs[:3],
        "headline": "What this road video supports",
        "summary": (
            f"{frames:,} sampled frames were analyzed. Vehicles were detected in "
            f"{vehicles:.1f}% of those frames; pedestrian detections appeared in {pedestrians:.1f}%. "
            f"Observed vehicle track IDs: {tracks['tracks']}. These are model observations, "
            "not independently validated traffic counts or proven accident risks."
        ),
        "limitations": (
            "Road classification based on filename is only a hint. "
            "Video alone does not establish legal speed, true distances without calibrated geometry, "
            "collision likelihood, road widening feasibility or reconstruction of hidden objects."
        ),
    }
