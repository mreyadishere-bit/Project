"""Conservative time-localized pedestrian/vehicle interaction review candidates.

An image-ground-point overlap is NOT an actual near miss. Only sustained
tracked proximity in a fixed video frame is surfaced for human inspection.
Metric TTC/PET, true distance, road use, and infrastructure are unobservable
without calibrated geometry and independent verification.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from math import hypot
from pathlib import Path

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle", "bicycle"}
MAX_EVENTS = 16


@dataclass(frozen=True)
class ReviewEvent:
    kind: str
    start_second: float
    end_second: float
    video_second: float
    person_track: str
    vehicle_track: str
    frame_count: int
    minimum_image_distance: float
    image_location: tuple[float, float]
    title: str = "Review possible pedestrian–vehicle interaction"
    confidence: str = "Provisional image-space evidence"
    explanation: str = (
        "Two continuously tracked participants had nearby image footpoints "
        "across several sampled frames. Perspective and occlusion mean this "
        "is NOT a verified conflict, unsafe crossing, or near miss."
    )


def find_interactions(objects_file, frame_width, frame_height, *,
                      distance_threshold=.085, minimum_frames=3,
                      min_duration=.35, max_events=MAX_EVENTS):
    """Stream file in frame order; bounded memory independent of clip length.

    Return time-localized review candidates, never asserted collision risks.
    A candidate requires independent stable vehicle and person track IDs.
    """
    if not objects_file or not Path(objects_file).is_file():
        return []
    width, height = int(frame_width or 0), int(frame_height or 0)
    if width <= 0 or height <= 0:
        return []
    active = {}
    episodes = []
    completed = []
    frame_key = None
    frame_rows = []

    def finish(key, episode):
        if (episode["n"] >= minimum_frames
                and episode["last"] - episode["start"] >= min_duration):
            completed.append(ReviewEvent(
                kind="image_space_interaction_candidate",
                start_second=round(episode["start"], 2),
                end_second=round(episode["last"], 2),
                video_second=round(episode["closest_t"], 2),
                person_track=key[0], vehicle_track=key[1],
                frame_count=episode["n"],
                minimum_image_distance=round(episode["min_dist"], 4),
                image_location=(round(episode["px"], 4),
                                round(episode["py"], 4)),
            ))

    def process_frame(rows):
        if not rows:
            return
        people, cars = {}, {}
        for row in rows:
            ident = str(row.get("track_id", "")).strip()
            cls = row.get("class", "")
            if not ident or ident.lower() in ("none", "nan", "-1"):
                continue
            try:
                px = float(row["center_x"]) / width
                py = float(row["y2"]) / height
                second = float(row["video_second"])
                conf = float(row.get("confidence") or 0)
            except (KeyError, ValueError, TypeError):
                continue
            if not (0 <= px <= 1 and 0 <= py <= 1 and conf >= .12):
                continue
            if cls == "person":
                people[ident] = (px, py, second)
            elif cls in VEHICLE_CLASSES:
                cars[f"{cls}:{ident}"] = (px, py, second)
        present = set()
        for person_id, (px, py, second) in people.items():
            for vehicle_id, (vx, vy, _) in cars.items():
                distance = hypot(px-vx, py-vy)
                if distance > distance_threshold:
                    continue
                key = (person_id, vehicle_id)
                present.add(key)
                ep = active.get(key)
                if ep is not None and 0 < second - ep["last"] <= 1.5:
                    ep["n"] += 1
                    ep["last"] = second
                else:
                    if ep:
                        finish(key, ep)
                    ep = {"start": second, "last": second, "n": 1,
                          "min_dist": distance, "closest_t": second,
                          "px": (px+vx)/2, "py": (py+vy)/2}
                    active[key] = ep
                if distance < ep["min_dist"]:
                    ep.update(min_dist=distance, closest_t=second,
                              px=(px+vx)/2, py=(py+vy)/2)
        for key in list(active):
            if key not in present:
                finish(key, active.pop(key))

    # Do not materialize the whole objects.csv in RAM.
    with Path(objects_file).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            identifier = row.get("frame_number")
            if frame_key is not None and identifier != frame_key:
                process_frame(frame_rows)
                frame_rows = []
            frame_key = identifier
            frame_rows.append(row)
        process_frame(frame_rows)
    for key, ep in active.items():
        finish(key, ep)
    # If one vehicle-person pair flickers it may make multiple episodes.
    # Keep distinct temporal windows and rank by duration & proximity.
    completed.sort(key=lambda e: (-e.frame_count, e.minimum_image_distance))
    unique = []
    for event in completed:
        if any(abs(event.video_second-old.video_second) < 1.5
               and hypot(*(a-b for a,b in zip(event.image_location, old.image_location))) < .06
               for old in unique):
            continue
        unique.append(event)
        if len(unique) >= max_events:
            break
    return [asdict(e) for e in sorted(unique, key=lambda e:e.video_second)]
