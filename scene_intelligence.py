"""Transparent, testable scene diagnostics for research road video.

Image-plane heuristics are observations, NOT accident prediction.
Metric speeds require explicit camera calibration and remain approximate.
"""
from __future__ import annotations

from math import hypot
from typing import Optional


def image_motion(previous, point, seconds: float, meters_per_pixel: Optional[float] = None):
    """Observed apparent motion per second, optionally uniform-scale speed estimate.

    previous: (x, y, video_second) from an earlier sampled frame.
    A single pixels-to-metres scale is not a perspective homography; it only
    approximates motion on a planar, fixed-camera view near the calibration region.
    """
    if previous is None:
        return None, None
    dx = float(point[0]) - float(previous[0])
    dy = float(point[1]) - float(previous[1])
    dt = float(seconds) - float(previous[2])
    if dt <= 0:
        return None, None
    px_s = hypot(dx, dy) / dt
    kmh = px_s * float(meters_per_pixel) * 3.6 if meters_per_pixel and meters_per_pixel > 0 else None
    return round(px_s, 2), round(kmh, 2) if kmh is not None else None


def visual_proximity(detections, frame_width: int, frame_height: int):
    """Return close pedestrian/vehicle pairs in image coordinates only.

    This MUST NOT be called a real-world near miss: perspective and depth are unknown.
    """
    vehicles = {"car", "bus", "truck", "motorcycle", "bicycle"}
    people = [d for d in detections if d.get("class") == "person"]
    cars = [d for d in detections if d.get("class") in vehicles]
    if frame_width <= 0 or frame_height <= 0:
        return []
    pairs = []
    for p in people:
        for v in cars:
            # Compare apparent contact points at bottoms of detection rectangles.
            px, py = (p["x1"] + p["x2"]) / 2, p["y2"]
            vx, vy = (v["x1"] + v["x2"]) / 2, v["y2"]
            scaled = hypot((px-vx)/frame_width, (py-vy)/frame_height)
            if scaled <= 0.075:
                pairs.append({"person_id": p.get("track_id"), "vehicle_id": v.get("track_id"),
                              "image_distance": round(scaled, 3)})
    return pairs


def scene_diagnostics(frame, detections, counts: dict):
    """Describe a frame with repeatable thresholds; no claims about road defects."""
    height, width = frame.shape[:2]
    # Array mean requires numpy, already available with OpenCV; NOT a lux reading.
    brightness = float(frame.mean())
    occupancy = sum(max(0, d["x2"] - d["x1"]) * max(0, d["y2"] - d["y1"]) for d in detections)
    occupancy_ratio = round(min(1.0, occupancy / max(1, width * height)), 3)
    proximity = visual_proximity(detections, width, height)
    return {
        "brightness": round(brightness, 1),
        "low_image_brightness": brightness < 48.0,
        "occupancy_ratio": occupancy_ratio,
        "dense_scene": int(counts.get("vehicles", 0)) >= 10 or occupancy_ratio > 0.55,
        "visual_proximity_pairs": len(proximity),
        "proximity_pairs": proximity,
    }


def diagnostic_events(diag: dict, second: float, last_emitted: dict, cooldown: float = 12.0):
    """Produce throttled, explicitly provisional observation events."""
    checks = [
        ("low_brightness", diag["low_image_brightness"], "Low image brightness",
         "Mean frame brightness is low; weather, exposure and time of day may affect it.", "observe"),
        ("dense_scene", diag["dense_scene"], "Crowded image view",
         "Many objects or large detections occupy the frame; this is not a congestion measurement.", "observe"),
        ("visual_proximity", diag["visual_proximity_pairs"] > 0, "Close in image",
         "Pedestrian and vehicle detections look close in pixels; distance and collision risk are unknown.", "review"),
    ]
    events = []
    for event_type, triggered, title, description, level in checks:
        last = last_emitted.get(event_type, float("-inf"))
        if triggered and second - last >= cooldown:
            events.append({"video_second": round(second, 2), "event_type": event_type,
                           "title": title, "description": description, "level": level})
            last_emitted[event_type] = second
    return events


def draw_scene_overlay(frame, detections):
    """Subtle professional object labels, instead of default multicolour plot().

    Image annotations are qualitative; image-plane velocities are not road speed.
    """
    import cv2
    annotated = frame.copy()
    height, width = annotated.shape[:2]
    for item in detections:
        category = str(item["class"])
        # OpenCV BGR — blue for vehicles, teal for people, subdued neutral for others.
        color = (214, 127, 42) if category in {"car", "truck", "bus", "motorcycle", "bicycle"} else (
            (156, 156, 36) if category == "person" else (170, 146, 123)
        )
        x1, y1 = int(max(0, min(width-1, item["x1"]))), int(max(0, min(height-1, item["y1"])))
        x2, y2 = int(max(0, min(width-1, item["x2"]))), int(max(0, min(height-1, item["y2"])))
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
        tag = category
        if item.get("track_id") not in (None, ""):
            tag += f"  #{item['track_id']}"
        tag += f"  {item['confidence']:.0%}"
        if item.get("calibrated_speed_kmh") is not None:
            tag += f"  ~{item['calibrated_speed_kmh']:.0f} km/h"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = .43 if width < 950 else .52
        thickness = 1
        (text_w, text_h), baseline = cv2.getTextSize(tag, font, scale, thickness)
        box_w = min(width-1, text_w+16)
        label_x = min(x1, max(0, width-box_w-1))
        # Keep label inside video bounds when an object touches the top edge.
        label_y = max(0, y1-text_h-baseline-13) if y1 >= text_h+baseline+13 else min(height-1, y1+2)
        cv2.rectangle(annotated, (label_x, label_y),
                      (label_x+box_w, min(height-1, label_y+text_h+baseline+13)),
                      (29, 41, 52), -1)
        cv2.putText(annotated, tag, (label_x+7, label_y+text_h+7),
                    font, scale, (250, 251, 252), thickness, cv2.LINE_AA)
    return annotated
