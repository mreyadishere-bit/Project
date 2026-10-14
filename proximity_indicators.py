"""Transparent proximity indicators for the video overlay and dashboard.

No monocular pixel separation is reported as metres or collision probability.
A metric indicator is possible only after explicit road-plane calibration.
These are review priorities, not safety certifications or crash predictions.
"""
from __future__ import annotations

from math import hypot, isfinite

VEHICLES = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})
RELEVANT = VEHICLES | {"person"}
LEVEL_ORDER = {"unknown": 0, "safe": 1, "caution": 2, "risk": 3, "critical": 4}
LEVEL_LABEL = {
    "unknown": "Not measured", "safe": "Measured spacing",
    "caution": "Check spacing", "risk": "Close approach",
    "critical": "Very close approach",
}
LEVEL_COLOR_BGR = {
    "unknown": (163, 143, 114),  # slate
    "safe": (125, 169, 43),       # green
    "caution": (45, 188, 245),    # amber
    "risk": (39, 119, 244),       # orange
    "critical": (69, 65, 225),    # red
}


def _track_id(row):
    value = row.get("track_id")
    return str(value) if value not in ("", None) else ""


def _world(row):
    try:
        x, y = float(row.get("world_x_m")), float(row.get("world_y_m"))
    except (TypeError, ValueError):
        return None
    return (x, y) if isfinite(x) and isfinite(y) else None


def _foot(row):
    return ((float(row["x1"]) + float(row["x2"])) / 2, float(row["y2"]))


def classify_metric_distance(distance_m, closing_m_s, pedestrian=False):
    """Heuristic attention tiers, not empirical collision-risk probabilities.

    Conservative pedestrian review radius is larger; no speed-limit inference.
    """
    if not isfinite(distance_m) or distance_m < 0:
        raise ValueError("Distance must be a finite, nonnegative number")
    approach = max(0.0, closing_m_s or 0.0)
    multiplier = 1.5 if pedestrian else 1.0
    if distance_m < .8 * multiplier or (distance_m < 1.8 * multiplier and approach >= 1):
        level = "critical"
    elif distance_m < 3.0 * multiplier or (distance_m < 5.0 * multiplier and approach >= 3.5):
        level = "risk"
    elif distance_m < 6.5 * multiplier or (distance_m < 9.0 * multiplier and approach >= 6):
        level = "caution"
    else:
        level = "safe"
    return level


def assess_proximity(detections, frame_width, frame_height, second, previous=None):
    """Annotate visible objects and return bounded, same-frame pair evidence.

    `previous` is a per-job dict for persistent pair distance (metres, time).
    Uncalibrated videos may show a *yellow* image-overlap review cue, never
    orange/red based on an unmeasured physical collision distance.
    """
    previous = {} if previous is None else previous
    for row in detections:
        row["risk_level"] = "unknown"
        row["risk_basis"] = "No calibrated pair measurement"
        row["nearest_distance_m"] = None
        row["closing_speed_kmh"] = None
    if frame_width < 2 or frame_height < 2:
        return {"level": "unknown", "pairs": [], "measured_pairs": 0,
                "image_review_pairs": 0, "closest_m": None}
    pairs = []
    relevant = [(i, d) for i, d in enumerate(detections)
                if d.get("class") in RELEVANT]
    active = set()
    for a_index, (i, a) in enumerate(relevant):
        for j, b in relevant[a_index + 1:]:
            a_name, b_name = a["class"], b["class"]
            if a_name == b_name == "person" or (a_name == "person" and b_name == "person"):
                continue
            if not (a_name in VEHICLES or b_name in VEHICLES):
                continue
            pedestrian = "person" in {a_name, b_name}
            # Apparent image separation is a review hint, not a metric distance.
            af, bf = _foot(a), _foot(b)
            image_distance = hypot((af[0] - bf[0]) / frame_width,
                                   (af[1] - bf[1]) / frame_height)
            aw, bw = _world(a), _world(b)
            metric = aw is not None and bw is not None
            if not metric and image_distance > 0.065:
                continue
            closing = None
            if metric:
                distance = hypot(aw[0] - bw[0], aw[1] - bw[1])
                aid, bid = _track_id(a), _track_id(b)
                pair_key = tuple(sorted((aid, bid))) if aid and bid and aid != bid else None
                if pair_key:
                    active.add(pair_key)
                    old = previous.get(pair_key)
                    if old is not None:
                        delta = second - old[1]
                        if 0.05 < delta <= 3.0:
                            closing = max(0.0, (old[0] - distance) / delta)
                    previous[pair_key] = (distance, second)
                level = classify_metric_distance(distance, closing, pedestrian)
                basis = "Calibrated flat road plane; verify camera survey and tracking"
            else:
                distance = None
                level = "caution"
                basis = "Image overlap only; physical separation and collision risk unknown"
            pair = {
                "a": i, "b": j, "type": "person–vehicle" if pedestrian else "vehicle–vehicle",
                "level": level, "distance_m": round(distance, 2) if distance is not None else None,
                "closing_kmh": round(closing * 3.6, 1) if closing is not None else None,
                "image_separation": round(image_distance, 4),
                "basis": basis, "second": round(second, 2),
            }
            pairs.append(pair)
            for row in (a, b):
                if LEVEL_ORDER[level] >= LEVEL_ORDER[row["risk_level"]]:
                    row["risk_level"] = level
                    row["risk_basis"] = basis
                    if metric:
                        row["nearest_distance_m"] = round(distance, 2)
                        row["closing_speed_kmh"] = pair["closing_kmh"]
    for key in list(previous):
        if key not in active:
            del previous[key]
    # Smallest physically measured gap and highest priority stay visible in UI.
    measured = [p for p in pairs if p["distance_m"] is not None]
    ranked = sorted(pairs, key=lambda p: (
        -LEVEL_ORDER[p["level"]], p["distance_m"] if p["distance_m"] is not None else float("inf")))
    highest = ranked[0]["level"] if ranked else "unknown"
    if not measured and ranked:
        highest = "caution"  # unverified image-space attention, never red
    return {"level": highest, "pairs": ranked[:12],
            "measured_pairs": len(measured),
            "image_review_pairs": len(pairs) - len(measured),
            "closest_m": min((p["distance_m"] for p in measured), default=None),
            "basis": "calibrated" if measured else "image-only"}
