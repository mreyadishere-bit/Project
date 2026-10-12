"""Long-running local road-video analysis and PC webcam monitoring.

No video duration cap. A worker thread processes frames and stores data to disk,
while Streamlit reads bounded snapshots. Not an accident or speed estimator.
"""
from __future__ import annotations

import csv
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
import uuid

import cv2

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
ROAD_CLASSES = ("person", "car", "motorcycle", "bus", "truck", "bicycle", "traffic light", "stop sign")
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}
SUMMARY_FIELDS = ["video_second", "frame_number", "people", "vehicles", "cars", "buses", "trucks", "motorcycles", "bicycles", "traffic_lights", "stop_signs", "all_objects"]
OBJECT_FIELDS = ["video_second", "frame_number", "track_id", "class", "confidence", "x1", "y1", "x2", "y2", "center_x", "center_y", "direction", "observed_at_utc"]


def motion_direction(previous: tuple[float, float] | None, current: tuple[float, float], threshold=8.0):
    """Rough direction in image pixels, NOT ground-plane heading or speed."""
    if previous is None:
        return "new"
    dx, dy = current[0] - previous[0], current[1] - previous[1]
    if max(abs(dx), abs(dy)) < threshold:
        return "still/unclear"
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def frame_counts(detections: list[dict]):
    classes = Counter(x["class"] for x in detections)
    return {
        "people": classes["person"], "vehicles": sum(classes[x] for x in VEHICLES),
        "cars": classes["car"], "buses": classes["bus"], "trucks": classes["truck"],
        "motorcycles": classes["motorcycle"], "bicycles": classes["bicycle"],
        "traffic_lights": classes["traffic light"], "stop_signs": classes["stop sign"],
        "all_objects": len(detections),
    }



class LatestCameraFrames:
    """Continuously drain camera buffers and retain only the newest frame.

    This avoids the multi-second backlog common when AI inference is slower
    than the camera frame rate. Requires locally attached camera access.
    """
    def __init__(self, capture, stop_event):
        self.capture = capture
        self.stop_event = stop_event
        self.condition = threading.Condition()
        self.frame = None
        self.version = 0
        self.failed = False
        self.thread = threading.Thread(target=self._read_loop, daemon=True, name="smartroad-camera")
        self.thread.start()

    def _read_loop(self):
        while not self.stop_event.is_set():
            ok, frame = self.capture.read()
            if not ok:
                with self.condition:
                    self.failed = True
                    self.condition.notify_all()
                break
            with self.condition:
                self.frame = frame
                self.version += 1
                self.condition.notify_all()

    def next_frame(self, last_version):
        with self.condition:
            self.condition.wait_for(lambda: self.version > last_version or self.failed or self.stop_event.is_set(), timeout=0.6)
            if self.version > last_version:
                return True, self.frame.copy(), self.version
            if self.failed:
                raise RuntimeError("Camera stopped returning frames. Is another app using it?")
            return False, None, last_version

    def close(self):
        self.thread.join(timeout=1.0)


@dataclass(frozen=True)
class VideoSettings:
    model_name: str = "yolo26n.pt"
    confidence: float = 0.35
    image_size: int = 640
    analysis_fps: int = 5   # file frames analysed per video second (approx.)
    all_classes: bool = False
    save_video: bool = False


class VideoJob:
    """One file or one PC camera, isolated model and tracker per job."""
    def __init__(self, source: str | int, settings: VideoSettings, label: str = "Video"):
        if settings.model_name not in {"yolo26n.pt", "yolo26s.pt", "yolo26m.pt"}:
            raise ValueError("Invalid model")
        if not 0.1 <= settings.confidence <= 0.95:
            raise ValueError("Invalid confidence")
        if settings.analysis_fps not in {1, 2, 5, 10, 15, 30}:
            raise ValueError("Invalid analysis rate")
        self.source = source
        self.settings = settings
        self.label = label[:120]
        self.is_camera = isinstance(source, int)
        self.id = uuid.uuid4().hex[:12]
        self.folder = OUTPUTS / self.id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.summary_file = self.folder / "frames.csv"
        self.objects_file = self.folder / "objects.csv"
        self.video_file = self.folder / "annotated.mp4"
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self.status = "starting"
        self.error = ""
        self.preview_jpeg: bytes | None = None
        self.total_frames = 0
        self.frames_read = 0
        self.analyzed_frames = 0
        self.duration_seconds = 0.0
        self.video_second = 0.0
        self.detected_now: dict = {}
        self.max_vehicles = 0
        self.max_people = 0
        self.unique_track_ids: set[int] = set()
        self.track_positions: dict[int, tuple[tuple[float, float], int]] = {}
        self.recent_frames: deque[dict] = deque(maxlen=180)
        self.recent_objects: deque[dict] = deque(maxlen=80)
        self.processing_fps = 0.0
        self.device = "not loaded"
        self.started_at = time.time()
        self.finished_at = None
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"smartroad-{self.id}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._pause.clear()

    def pause(self):
        if not self.is_camera:
            self._pause.set()

    def resume(self):
        self._pause.clear()

    def snapshot(self):
        with self._lock:
            return {
                "status": self.status, "error": self.error, "label": self.label,
                "preview_jpeg": self.preview_jpeg, "duration_seconds": self.duration_seconds,
                "video_second": self.video_second, "total_frames": self.total_frames,
                "frames_read": self.frames_read, "analyzed_frames": self.analyzed_frames,
                "detected_now": dict(self.detected_now), "max_vehicles": self.max_vehicles,
                "max_people": self.max_people, "unique_tracks": len(self.unique_track_ids),
                "recent_frames": list(self.recent_frames), "recent_objects": list(self.recent_objects),
                "processing_fps": self.processing_fps, "device": self.device,
                "paused": self._pause.is_set(), "is_camera": self.is_camera,
                "folder": str(self.folder), "finished_at": self.finished_at,
            }

    def _run(self):
        cap = None
        writer = None
        camera_reader = None
        try:
            # Load model on the worker thread to avoid freezing UI.
            from ultralytics import YOLO
            import torch
            device = "0" if torch.cuda.is_available() else "cpu"
            with self._lock:
                self.device = "GPU (CUDA)" if device == "0" else "CPU"
                self.status = "loading model"
            model = YOLO(self.settings.model_name)
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                raise ValueError("Cannot open source. Check file path or camera permissions / camera index.")
            if self.is_camera:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                camera_reader = LatestCameraFrames(cap, self._stop)
            video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            if not (1 <= video_fps <= 240):
                video_fps = 30.0
            total_frames = 0 if self.is_camera else max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
            frame_step = max(1, round(video_fps / self.settings.analysis_fps)) if not self.is_camera else 1
            model_classes = model.names
            if self.settings.all_classes:
                class_ids = None
            else:
                class_ids = [int(i) for i, name in model_classes.items() if name in ROAD_CLASSES] if isinstance(model_classes, dict) else [i for i, name in enumerate(model_classes) if name in ROAD_CLASSES]
            with self._lock:
                self.duration_seconds = total_frames / video_fps if total_frames else 0
                self.total_frames = total_frames
                self.status = "running"

            times: deque[float] = deque(maxlen=25)
            i = 0
            last_camera_version = 0
            live_start = time.monotonic()
            previous_points: dict[int, tuple[float, float]] = {}
            with self.summary_file.open("w", encoding="utf-8-sig", newline="") as summaries, self.objects_file.open("w", encoding="utf-8-sig", newline="") as objects:
                summary_csv = csv.DictWriter(summaries, fieldnames=SUMMARY_FIELDS)
                object_csv = csv.DictWriter(objects, fieldnames=OBJECT_FIELDS)
                summary_csv.writeheader()
                object_csv.writeheader()
                while not self._stop.is_set():
                    if self._pause.is_set():
                        time.sleep(0.12)
                        continue
                    # Grab rather than decode non-sampled frames, to reduce overhead.
                    if not self.is_camera and i % frame_step:
                        if not cap.grab():
                            break
                        i += 1
                        continue
                    if self.is_camera:
                        ok, frame, last_camera_version = camera_reader.next_frame(last_camera_version)
                        if not ok:
                            continue  # A slow/no frame interval, not necessarily a failure.
                    else:
                        ok, frame = cap.read()
                        if not ok:
                            break
                    frame_no = i
                    i += 1
                    seconds = (time.monotonic() - live_start) if self.is_camera else frame_no / video_fps
                    if self.is_camera and frame_no == 0:
                        live_start = time.monotonic()
                        seconds = 0.0
                    # Keep memory/inference reasonable for high-resolution video.
                    height, width = frame.shape[:2]
                    if width > 1600:
                        new_size = (1600, round(height * 1600 / width))
                        frame = cv2.resize(frame, new_size)
                    tracked = model.track(frame, persist=True, tracker="bytetrack.yaml", classes=class_ids,
                                          imgsz=self.settings.image_size, conf=self.settings.confidence,
                                          device=device, verbose=False)[0]
                    detections = []
                    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    if tracked.boxes is not None and len(tracked.boxes):
                        xyxy = tracked.boxes.xyxy.cpu().tolist()
                        probs = tracked.boxes.conf.cpu().tolist()
                        cls_ids = tracked.boxes.cls.int().cpu().tolist()
                        ids = tracked.boxes.id.int().cpu().tolist() if tracked.boxes.id is not None else [None] * len(xyxy)
                        for bounds, confidence, cls_id, track_id in zip(xyxy, probs, cls_ids, ids):
                            class_name = tracked.names[cls_id]
                            x1, y1, x2, y2 = [round(float(v), 1) for v in bounds]
                            center = ((x1 + x2) / 2, (y1 + y2) / 2)
                            direction = motion_direction(previous_points.get(track_id), center) if track_id is not None else "untracked"
                            if track_id is not None:
                                previous_points[track_id] = center
                            detections.append({
                                "video_second": round(seconds, 2), "frame_number": frame_no,
                                "track_id": "" if track_id is None else int(track_id),
                                "class": class_name, "confidence": round(float(confidence), 3),
                                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                "center_x": round(center[0], 1), "center_y": round(center[1], 1),
                                "direction": direction, "observed_at_utc": now_iso,
                            })
                    counts = frame_counts(detections)
                    entry = {"video_second": round(seconds, 2), "frame_number": frame_no, **counts}
                    summary_csv.writerow(entry)
                    object_csv.writerows(detections)
                    if frame_no % 60 == 0:
                        summaries.flush()
                        objects.flush()
                    # Prune positions of inactive tracks, without resetting unique-ID count.
                    active_ids = {int(d["track_id"]) for d in detections if d["track_id"] != ""}
                    for track_id in list(previous_points):
                        if track_id not in active_ids:
                            del previous_points[track_id]
                    annotated = tracked.plot()
                    if self.settings.save_video and not self.is_camera:
                        if writer is None:
                            h, w = annotated.shape[:2]
                            output_rate = video_fps / frame_step
                            writer = cv2.VideoWriter(str(self.video_file), cv2.VideoWriter_fourcc(*"mp4v"), output_rate, (w, h))
                            if not writer.isOpened():
                                raise RuntimeError("Cannot create annotated MP4. Retry with Export video unchecked.")
                        writer.write(annotated)
                    # Browser preview limited to one JPEG, not all past frames.
                    h, w = annotated.shape[:2]
                    preview = cv2.resize(annotated, (min(w, 960), round(h * min(w, 960) / w))) if w > 960 else annotated
                    encoded_ok, buffer = cv2.imencode(".jpg", preview, [cv2.IMWRITE_JPEG_QUALITY, 72])
                    times.append(time.monotonic())
                    elapsed = times[-1] - times[0] if len(times) > 1 else 0
                    with self._lock:
                        self.preview_jpeg = buffer.tobytes() if encoded_ok else None
                        self.frames_read = i
                        self.analyzed_frames += 1
                        self.video_second = seconds
                        self.detected_now = counts
                        self.max_vehicles = max(self.max_vehicles, counts["vehicles"])
                        self.max_people = max(self.max_people, counts["people"])
                        self.unique_track_ids.update(active_ids)
                        self.recent_frames.append(entry)
                        self.recent_objects.extend(detections[-30:])
                        self.processing_fps = (len(times) - 1) / elapsed if elapsed > 0 else 0
            with self._lock:
                self.status = "stopped" if self._stop.is_set() else "completed"
        except Exception as exc:
            with self._lock:
                self.error = f"{type(exc).__name__}: {exc}"
                self.status = "error"
        finally:
            self._stop.set()  # Ensure camera reader can leave its loop.
            if camera_reader is not None:
                camera_reader.close()
            if writer is not None:
                writer.release()
            if cap is not None:
                cap.release()
            with self._lock:
                self.finished_at = time.time()
