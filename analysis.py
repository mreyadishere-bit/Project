"""AI vehicle/person detector, not a validated accident prediction model."""
from pathlib import Path
import cv2

VEHICLE_CLASSES = {"car", "bus", "truck", "motorcycle", "bicycle"}


def demo_index(max_vehicles, max_pedestrians):
    """Display-only vehicle-density / proximity-candidate indicator, NOT accident probability."""
    return min(70, max(0, max_vehicles - 2) * 9
               + (12 if max_vehicles and max_pedestrians else 0)
               + max(0, max_pedestrians - 2) * 6)


def analyze_video(video_path, progress=None, seconds_between_samples=1.5, maximum_seconds=None):
    from ultralytics import YOLO
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError("Could not read the video. Try converting it to MP4/H.264.")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 0:
            fps = 25
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sample_every = max(1, round(fps * seconds_between_samples))
        # Legacy sampled analyser: no arbitrary maximum duration by default.
        # Video Intelligence v2 uses a background thread and streaming CSV instead.
        target = min(count, round(fps * maximum_seconds)) if (count and maximum_seconds is not None) else (round(fps * maximum_seconds) if maximum_seconds is not None else (count or None))
        estimated_samples = max(1, ((target + sample_every - 1) // sample_every) if target is not None else 1)
        model = YOLO("yolo26n.pt")  # first run downloads official weights
        rows, preview_rgb = [], None
        frame_index = 0
        while target is None or frame_index < target:
            success, frame = cap.read()
            if not success:
                break
            if frame_index % sample_every == 0:
                result = model.predict(frame, conf=0.35, imgsz=512, verbose=False, device="cpu")[0]
                vehicle_count, people_count = 0, 0
                if result.boxes is not None:
                    for cls in result.boxes.cls.tolist():
                        label = result.names[int(cls)]
                        if label in VEHICLE_CLASSES:
                            vehicle_count += 1
                        elif label == "person":
                            people_count += 1
                rows.append({"الثانية": round(frame_index / fps, 1),
                             "مركبات": vehicle_count, "مشاة": people_count})
                preview_rgb = cv2.cvtColor(result.plot(), cv2.COLOR_BGR2RGB)
                if progress:
                    if target is not None:
                        progress(min(1.0, len(rows) / estimated_samples))
            frame_index += 1
        if not rows:
            raise ValueError("No frames could be analysed. Try another MP4 file.")
        max_vehicles = max(r["مركبات"] for r in rows)
        max_people = max(r["مشاة"] for r in rows)
        return {"samples": rows, "preview_rgb": preview_rgb,
                "max_vehicles": max_vehicles, "max_people": max_people,
                "demo_index": demo_index(max_vehicles, max_people)}
    finally:
        cap.release()
