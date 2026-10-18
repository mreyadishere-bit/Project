"""Dr. Traffic | evidence-first prototype.

An annotated traffic video creates REVIEW CANDIDATES, not legally established
violations. Tracking, detection and manually entered signal timing are separate
sources. No plate reading, litter detection or physical speed is claimed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path
from typing import Callable

VEHICLES = {"car", "truck", "bus", "motorcycle", "bicycle"}
ROAD_USERS = VEHICLES | {"person"}
MAX_EVENTS = 120
MAX_OBSERVATIONS = 6000


@dataclass(frozen=True)
class ReviewSettings:
    model_name: str = "yolo26n.pt"
    tracker: str = "bytetrack.yaml"
    image_size: int = 640
    analysis_fps: int = 3
    confidence: float = 0.26
    stop_line_y: float = 0.58
    direction: str = "down"
    manually_verified_red: bool = False
    red_start: float = 0.0
    red_end: float = 0.0

    def validate(self):
        if self.tracker not in {"bytetrack.yaml", "botsort.yaml"}:
            raise ValueError("Unsupported tracking algorithm.")
        if self.model_name not in {"yolo26n.pt", "yolo26s.pt"}:
            raise ValueError("Unsupported detection model.")
        if self.direction not in {"down", "up"}:
            raise ValueError("Crossing direction must be up or down.")
        if not 1 <= self.analysis_fps <= 15 or self.image_size not in {480, 640, 832}:
            raise ValueError("Invalid analysis settings.")
        if not 0.1 <= self.confidence <= 0.9 or not 0.05 <= self.stop_line_y <= 0.95:
            raise ValueError("Invalid detection or line settings.")
        if self.manually_verified_red and not 0 <= self.red_start < self.red_end:
            raise ValueError("A confirmed red signal needs valid start and end times.")


def crossed_line(old_y, current_y, line_y, direction):
    """Image-footpoint crossing; not proof of crossing a physical stop line."""
    if direction == "down":
        return old_y < line_y <= current_y
    if direction == "up":
        return old_y > line_y >= current_y
    raise ValueError("Unsupported direction.")


def observe_crossings(objects, history, *, video_second, settings):
    """Generate at most one temporal candidate per tracked vehicle.

    Only the user-specified RED interval is considered: color is NOT inferred
    from vehicle detection. A track must have two recent stable observations.
    """
    candidates = []
    for obj in objects:
        ident = obj.get("track_id")
        if ident is None or obj.get("class") not in VEHICLES:
            continue
        try:
            foot = float(obj["bbox"][3])
            height = float(obj["frame_height"])
            y = foot / height
        except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError):
            continue
        if not 0 <= y <= 1:
            continue
        key = f"{obj['class']}:{ident}"
        old = history.get(key)
        if old is not None:
            previous_y, previous_t, previously_crossed = old
        else:
            previous_y, previous_t, previously_crossed = y, video_second, False
        valid_gap = 0 < video_second - previous_t <= 2.0
        crossed = valid_gap and not previously_crossed and crossed_line(
            previous_y, y, settings.stop_line_y, settings.direction
        )
        if crossed:
            in_red = (
                settings.manually_verified_red
                and settings.red_start <= video_second <= settings.red_end
            )
            title = (
                "Possible stop-line crossing during manually marked red phase"
                if in_red else "Vehicle crossed the marked review line"
            )
            candidates.append({
                "type": "possible_red_signal_crossing" if in_red else "line_crossing_observation",
                "title": title,
                "timestamp_seconds": round(video_second, 2),
                "track_id": str(ident),
                "object_type": obj["class"],
                "severity": "review" if in_red else "observation",
                "confirmed_violation": False,
                "signal_status": "manually_marked_red" if in_red else "not_verified",
                "evidence": "Tracked vehicle footpoint crossed the user-set image line between sampled frames.",
                "limitations": (
                    "The line is an image approximation, signal timing is user-entered "
                    "and no legal infraction is automatically established."
                ),
                "bounding_box": obj["bbox"],
            })
        history[key] = (y, video_second, previously_crossed or bool(crossed))
    return candidates


def _detections(result, height, width):
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []
    coords = boxes.xyxy.cpu().tolist()
    classes = boxes.cls.int().cpu().tolist()
    scores = boxes.conf.cpu().tolist()
    track_data = getattr(boxes, "id", None)
    ids = track_data.int().cpu().tolist() if track_data is not None else [None] * len(classes)
    names = getattr(result, "names", {})
    output = []
    for bounds, cls_id, score, ident in zip(coords, classes, scores, ids):
        name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id]
        if name not in ROAD_USERS | {"traffic light", "stop sign"}:
            continue
        x1, y1, x2, y2 = (round(float(v), 1) for v in bounds)
        output.append({
            "class": name, "confidence": round(float(score), 3),
            "track_id": int(ident) if ident is not None else None,
            "bbox": [x1, y1, x2, y2],
            "frame_height": height, "frame_width": width
        })
    return output


def analyze_video(
    path: str | Path,
    *,
    settings: ReviewSettings | None = None,
    progress: Callable[[float, str], None] | None = None,
    model=None,
    capture=None,
):
    """Analyze a local authorized recording, with bounded JSON/evidence memory.

    Model and capture injection make engine regression-testable without weights.
    Does not call external services with the footage.
    """
    import cv2
    settings = settings or ReviewSettings()
    settings.validate()
    local_path = Path(path)
    if capture is None:
        if not local_path.is_file():
            raise FileNotFoundError("Recording was not found.")
        capture = cv2.VideoCapture(str(local_path))
    if not capture.isOpened():
        raise RuntimeError("This recording could not be decoded.")
    if model is None:
        from ultralytics import YOLO
        model = YOLO(settings.model_name)

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    duration_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    trusted_fps = fps if 1 <= fps <= 240 else None
    step = max(1, round(trusted_fps / settings.analysis_fps)) if trusted_fps else 1
    observations, events, evidence = [], [], {}
    hist, counts = {}, {"car": 0, "truck": 0, "bus": 0, "motorcycle": 0, "bicycle": 0, "person": 0}
    peak_visible = 0
    processed = 0
    frame_index = 0
    first_detected = 0
    truncated = False
    try:
        while True:
            if frame_index % step:
                ok = capture.grab()
                frame_index += 1
                if not ok:
                    break
                continue
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            processed += 1
            height, width = frame.shape[:2]
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if not 0 < timestamp < 1e8:
                timestamp = (frame_index - 1) / trusted_fps if trusted_fps else None
            if timestamp is None:
                # Don't fabricate timestamps for an unknown frame rate.
                hist.clear()
            result = model.track(
                frame, persist=True, tracker=settings.tracker,
                conf=settings.confidence, imgsz=settings.image_size, verbose=False
            )[0]
            objects = _detections(result, height, width)
            if objects:
                first_detected += 1
            peak_visible = max(peak_visible, sum(o["class"] in VEHICLES for o in objects))
            for cls in counts:
                counts[cls] += sum(o["class"] == cls for o in objects)
            if len(observations) < MAX_OBSERVATIONS:
                observations.append({
                    "frame": frame_index - 1,
                    "timestamp_seconds": round(timestamp, 2) if timestamp is not None else None,
                    "detections": [{k: v for k, v in o.items() if k not in {"frame_height", "frame_width"}} for o in objects]
                })
            else:
                truncated = True

            if timestamp is not None and len(events) < MAX_EVENTS:
                found = observe_crossings(objects, hist, video_second=timestamp, settings=settings)
                for event in found[:MAX_EVENTS-len(events)]:
                    event_idx = len(events)
                    events.append(event)
                    if len(evidence) < 24:
                        marked = frame.copy()
                        x1, y1, x2, y2 = (int(v) for v in event["bounding_box"])
                        cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 174, 245), 3)
                        line = int(settings.stop_line_y * height)
                        cv2.line(marked, (0, line), (width - 1, line), (0, 174, 245), 2)
                        if width > 1000:
                            marked = cv2.resize(marked, (1000, round(height*1000/width)))
                        success, image = cv2.imencode(".jpg", marked, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        if success:
                            evidence[event_idx] = image.tobytes()

            if progress is not None and (processed == 1 or processed % 8 == 0):
                fraction = min(1.0, frame_index / duration_frames) if duration_frames > 0 else 0
                progress(fraction, f"Inspected {processed:,} sampled frames")
    finally:
        capture.release()

    if processed == 0:
        raise RuntimeError("There were no decodable frames in this recording.")
    report = {
        "schema_version": "dr-traffic-review-1",
        "source_filename": local_path.name,
        "status": "completed",
        "model": settings.model_name,
        "tracker": settings.tracker,
        "settings": asdict(settings),
        "coverage": {
            "sampled_frames": processed,
            "frames_with_detections": first_detected,
            "sample_interval_source_frames": step,
            "source_fps": trusted_fps,
            "timestamp_basis": "source_timing_or_fps" if trusted_fps else "missing_unknown",
            "all_frames_inspected": step == 1,
            "observations_truncated": truncated,
        },
        "metrics": {"peak_vehicles_in_sample": peak_visible, "sampled_object_observations": counts},
        "events": events,
        "observations": observations,
        "limitations": [
            "Events are review candidates, never legally verified violations.",
            "Manual red-light timing and the stop line must be independently verified.",
            "No physical speed, distances or collision probabilities are measured.",
            "No license plate OCR, litter detection or vehicle ownership lookup is performed.",
            "Counts refer to sampled detections, not independently verified unique vehicles."
        ],
    }
    if progress is not None:
        progress(1, f"Completed {processed:,} sampled frames")
    return report, evidence


def serialise_json(report: dict) -> bytes:
    return json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
