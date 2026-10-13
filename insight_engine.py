"""Evidence-first road video analytics and explainable review suggestions.

Online accumulation uses bounded memory even for long recordings.
These are image-plane observations, NOT certified safety scores,
real-world speeds, lane recognition or accident predictions.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle", "bicycle"}


@dataclass
class EvidenceAccumulator:
    grid_width: int = 14
    grid_height: int = 8
    frames: int = 0
    frames_with_vehicles: int = 0
    frames_with_people: int = 0
    low_light_frames: int = 0
    close_image_frames: int = 0
    busy_frames: int = 0
    total_vehicles_visible: int = 0
    total_people_visible: int = 0
    max_vehicles: int = 0
    total_brightness: float = 0.
    motion_samples: int = 0
    sum_motion_px_s: float = 0.
    events_by_type: Counter = field(default_factory=Counter)
    object_observations: Counter = field(default_factory=Counter)
    first_track_seen: dict = field(default_factory=dict)
    tracks_by_class: Counter = field(default_factory=Counter)
    # Do not let track memory grow forever for long live streams.
    tracked_id_limit: int = 30_000
    location_grid: list = field(default_factory=lambda: [[0]*14 for _ in range(8)])

    def observe(self, detections: list[dict], counts: dict, diagnostics: dict, *,
                second: float, frame_width: int, frame_height: int, events=()):
        self.frames += 1
        vehicles = int(counts.get("vehicles", 0))
        people = int(counts.get("people", 0))
        self.total_vehicles_visible += vehicles
        self.total_people_visible += people
        self.max_vehicles = max(self.max_vehicles, vehicles)
        self.frames_with_vehicles += vehicles > 0
        self.frames_with_people += people > 0
        self.low_light_frames += bool(diagnostics.get("low_image_brightness"))
        self.close_image_frames += int(diagnostics.get("visual_proximity_pairs", 0) > 0)
        self.busy_frames += bool(diagnostics.get("dense_scene"))
        self.total_brightness += float(diagnostics.get("brightness", 0.))
        for event in events:
            self.events_by_type[event["event_type"]] += 1
        width = max(1, frame_width)
        height = max(1, frame_height)
        for d in detections:
            cls = d["class"]
            self.object_observations[cls] += 1
            identifier = d.get("track_id")
            if isinstance(identifier, int):
                key = (cls, identifier)
                if key not in self.first_track_seen and len(self.first_track_seen) < self.tracked_id_limit:
                    self.first_track_seen[key] = round(second, 1)
                    self.tracks_by_class[cls] += 1
            motion = d.get("image_motion_px_s")
            if motion is not None:
                self.motion_samples += 1
                self.sum_motion_px_s += float(motion)
            # Contact point in image pixels, with identical bins across frames.
            x = ((float(d["x1"]) + float(d["x2"])) / 2) / width
            y = float(d["y2"]) / height
            col = max(0, min(self.grid_width-1, int(x*self.grid_width)))
            row = max(0, min(self.grid_height-1, int(y*self.grid_height)))
            self.location_grid[row][col] += 1

    def snapshot(self) -> dict:
        n = max(1, self.frames)
        fractions = {
            "vehicles": round(100*self.frames_with_vehicles/n, 1),
            "pedestrians": round(100*self.frames_with_people/n, 1),
            "dark_image": round(100*self.low_light_frames/n, 1),
            "close_in_image": round(100*self.close_image_frames/n, 1),
            "crowded_image": round(100*self.busy_frames/n, 1),
        }
        return {
            "analyzed_frames": self.frames,
            "averages_per_frame": {
                "vehicles": round(self.total_vehicles_visible/n, 2),
                "people": round(self.total_people_visible/n, 2)
            },
            "percent_of_sampled_frames": fractions,
            "average_image_brightness": round(self.total_brightness/n, 1),
            "mean_image_motion_px_s": (round(self.sum_motion_px_s/self.motion_samples, 1)
                                        if self.motion_samples else None),
            "unique_track_ids_by_class": dict(self.tracks_by_class),
            "sampled_frame_detections_by_class": dict(self.object_observations),
            "diagnostic_event_counts": dict(self.events_by_type),
            "footpoint_activity_grid": [list(row) for row in self.location_grid],
            "hotspot": self._hotspot(),
        }

    def _hotspot(self):
        data = [(count, x, y) for y, row in enumerate(self.location_grid)
                for x, count in enumerate(row)]
        if not data or max(data)[0] == 0:
            return None
        n, x, y = max(data)
        return {"column": x, "row": y, "observations": n,
                "x_fraction": round((x+.5)/self.grid_width, 3),
                "y_fraction": round((y+.5)/self.grid_height, 3)}


def review_priority(evidence: dict) -> dict:
    """A transparent attention index for TRIAGE, never a likelihood of a crash."""
    frames = evidence.get("analyzed_frames", 0)
    if frames < 10:
        return {"score": None, "level": "Insufficient data",
                "explanation": "At least 10 sampled frames are needed for a useful overview."}
    p = evidence["percent_of_sampled_frames"]
    # Explicit heuristic; no trained model and no safety probability claims.
    value = round(min(100, .35*p["close_in_image"] + .30*p["dark_image"] +
                      .20*p["crowded_image"] + .15*p["pedestrians"]))
    level = "Review sooner" if value >= 45 else ("Review" if value >= 20 else "Routine review")
    return {"score": value, "level": level,
            "explanation": "Heuristic weighted percentage of sampled frames that merit human review; NOT accident risk, enforcement, or a road-safety rating."}


def suggestions(evidence: dict) -> list[dict]:
    """Propose reviews based only on explicit observable triggers.

    Every proposed intervention must be confirmed by a qualified road engineer.
    """
    if evidence.get("analyzed_frames", 0) < 10:
        return [{"id": "more_video", "priority": "first",
                 "title": "Collect a more representative video sample",
                 "reason": "Fewer than 10 sampled frames are available.",
                 "action": "Analyze footage covering typical traffic patterns and different times.",
                 "verify": "Confirm coverage of the whole segment, relevant road users and lighting.",
                 "simulation_option": None}]
    p = evidence["percent_of_sampled_frames"]
    output = []
    if p["close_in_image"] >= 3:
        output.append({
            "id": "crossing_review", "priority": "high",
            "title": "Review pedestrian crossing layout and separation",
            "reason": f"Vehicle and pedestrian detections appeared close in {p['close_in_image']:.1f}% of sampled frames (image coordinates only).",
            "action": "Conduct an on-site survey: inspect crossing markings, refuges, pedestrian visibility and traffic movements; consider a marked crossing if justified.",
            "verify": "Measure site geometry, actual vehicle speeds, pedestrian flows and post-intervention conflicts.",
            "simulation_option": "crossing"})
    if p["dark_image"] >= 10:
        output.append({
            "id": "lighting_review", "priority": "medium",
            "title": "Inspect nighttime visibility and camera exposure",
            "reason": f"Raw image brightness was low in {p['dark_image']:.1f}% of sampled frames; this is not a lux measurement.",
            "action": "Check lighting on site, sign reflectivity and whether the camera's exposure causes dark frames.",
            "verify": "Use a lux meter and measurements under matching conditions.",
            "simulation_option": "lighting"})
    if p["crowded_image"] >= 10 or evidence["averages_per_frame"]["vehicles"] >= 8:
        output.append({
            "id": "flow_review", "priority": "medium",
            "title": "Review potential bottlenecks and traffic organization",
            "reason": f"Crowded image heuristic appeared in {p['crowded_image']:.1f}% of sampled frames.",
            "action": "Observe queue lengths, lane usage, junction timing and unexpected roadside stopping during peak periods.",
            "verify": "Collect surveyed vehicle counts, travel times and queue measurements; camera occupancy is not congestion.",
            "simulation_option": "flow"})
    if p["pedestrians"] >= 15 and p["vehicles"] >= 20:
        output.append({
            "id": "speed_review", "priority": "medium",
            "title": "Evaluate approach speeds around pedestrian activity",
            "reason": f"Pedestrians appeared in {p['pedestrians']:.1f}% and vehicles in {p['vehicles']:.1f}% of sampled frames.",
            "action": "Review speed management and crossing approaches; consider traffic calming only after an engineering study.",
            "verify": "Measure actual speeds and stopping distances with calibrated equipment.",
            "simulation_option": "speed"})
    if not output:
        output.append({
            "id": "routine", "priority": "routine",
            "title": "Complete an on-site safety review",
            "reason": "This video alone did not exceed the available experimental heuristics.",
            "action": "Review road condition, pedestrian access, signage and speeds under different conditions.",
            "verify": "A lack of automated flags cannot establish a road is safe.",
            "simulation_option": None})
    return output


def explain_video(evidence: dict, source: str, *, sampled_fps: int | None = None) -> dict:
    """Plain-language executive narrative, deterministically tied to real counts."""
    frames = evidence.get("analyzed_frames", 0)
    rates = evidence.get("percent_of_sampled_frames", {})
    avgs = evidence.get("averages_per_frame", {})
    score = review_priority(evidence)
    recs = suggestions(evidence)
    if not frames:
        return {"headline": "No video evidence analyzed",
                "description": "The system did not process any video frames. No claims about the road can be made.",
                "priority": score, "recommendations": recs}
    narrative = (
        f"Analyzed {frames:,} sampled frames from {source}. "
        f"An average sampled frame contained {avgs.get('vehicles', 0):.1f} visible vehicles "
        f"and {avgs.get('people', 0):.1f} visible pedestrians. "
        f"Pedestrians appeared in {rates.get('pedestrians', 0):.1f}% of frames; "
        f"low image brightness in {rates.get('dark_image', 0):.1f}%; and "
        f"close pedestrian–vehicle detections in image coordinates in "
        f"{rates.get('close_in_image', 0):.1f}%. "
        "These image measurements are experimental. Real speeds, collision risks "
        "and pavement condition cannot be established from these metrics alone."
    )
    return {"headline": "Video evidence summary", "description": narrative,
            "priority": score, "recommendations": recs}
