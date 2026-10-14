"""Long-running local road-video analysis and PC webcam monitoring.

No video duration cap. A worker thread processes frames and stores data to disk,
while Streamlit reads bounded snapshots. Not an accident or speed estimator.
"""
from __future__ import annotations

import csv
import os
import subprocess
import shutil
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
import uuid

import cv2
from scene_intelligence import image_motion, scene_diagnostics, diagnostic_events, draw_scene_overlay
from insight_engine import EvidenceAccumulator
from traffic_geometry import RoadCalibration, CrossingCounter, ground_kinematics
from road_tracking import RoadTracker, model_detections

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
LIVE_STREAM_SLOTS = threading.BoundedSemaphore(1)  # public hosted live CPU inference is bounded
ROAD_CLASSES = ("person", "car", "motorcycle", "bus", "truck", "bicycle", "traffic light", "stop sign")
VEHICLES = {"car", "motorcycle", "bus", "truck", "bicycle"}
SUMMARY_FIELDS = ["video_second", "frame_number", "people", "vehicles", "cars", "buses", "trucks", "motorcycles", "bicycles", "traffic_lights", "stop_signs", "all_objects"]
OBJECT_FIELDS = ["video_second", "frame_number", "track_id", "class", "confidence", "x1", "y1", "x2", "y2", "center_x", "center_y", "direction", "image_motion_px_s", "calibrated_speed_kmh", "world_x_m", "world_y_m", "heading_deg", "observed_at_utc"]
EVENT_FIELDS = ["video_second", "event_type", "title", "description", "level"]
CROSSING_FIELDS = ["second", "track_id", "class", "direction"]


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
    def __init__(self, capture, stop_event, reconnect_factory=None):
        self.capture = capture
        self.reconnect_factory = reconnect_factory
        self.failure_reason = "Video stream stopped returning frames."
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
                if self.reconnect_factory and not self.stop_event.is_set():
                    self.capture.release()
                    reconnected = False
                    for attempt in range(3):
                        if self.stop_event.wait(2 * (attempt + 1)):
                            break
                        try:
                            new_capture = self.reconnect_factory()
                            if new_capture.isOpened():
                                self.capture = new_capture
                                reconnected = True
                                break
                            new_capture.release()
                        except Exception as exc:
                            self.failure_reason = str(exc)[:250]
                    if reconnected:
                        continue
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
                raise RuntimeError(self.failure_reason)
            return False, None, last_version

    def close(self):
        self.thread.join(timeout=1.0)
        self.capture.release()


@dataclass(frozen=True)
class VideoSettings:
    model_name: str = "yolo26n.pt"
    confidence: float = 0.18
    image_size: int = 640
    analysis_fps: int = 5   # file frames analysed per video second (approx.)
    detail_scan_every: int = 8  # optional one extra small-object tile inference per N analyzed recording frames
    all_classes: bool = False
    save_video: bool = False
    meters_per_pixel: float | None = None   # legacy rough pixel scale
    road_calibration: RoadCalibration | None = None
    camera_fov_deg: float = 70.0  # needs real intrinsics for accurate pose
    count_line_fraction: float = .50
    tracker: str = "traffic_botsort.yaml"
    use_openvino: bool = False
    roi_rect: tuple[float,float,float,float] | None = None  # full video fractions (left, top, right, bottom)


class VideoJob:
    """One file, PC camera, or approved public live feed, isolated per worker."""
    def __init__(self, source: str | int, settings: VideoSettings, label: str = "Video", source_kind: str = "file"):
        if settings.model_name not in {"yolo26n.pt", "yolo26s.pt", "yolo26m.pt"}:
            raise ValueError("Invalid model")
        if not 0.1 <= settings.confidence <= 0.95:
            raise ValueError("Invalid confidence")
        if settings.analysis_fps not in {1, 2, 5, 10, 15, 30}:
            raise ValueError("Invalid analysis rate")
        if settings.detail_scan_every not in (0, 4, 6, 8, 12, 16):
            raise ValueError("Invalid detail scan interval")
        if not 30 <= settings.camera_fov_deg <= 120:
            raise ValueError("Camera FOV outside supported range")
        if settings.roi_rect is not None:
            x0,y0,x1,y1=settings.roi_rect
            if not (0<=x0<x1<=1 and 0<=y0<y1<=1 and x1-x0>=.18 and y1-y0>=.18):
                raise ValueError("Road detection focus rectangle is invalid.")
        if settings.tracker not in {"botsort.yaml", "bytetrack.yaml", "traffic_botsort.yaml"}:
            raise ValueError("Invalid tracker")
        if not .05 <= settings.count_line_fraction <= .95:
            raise ValueError("Invalid counting-line position")
        if source_kind not in {"file", "youtube", "public_live"}:
            raise ValueError("Unsupported source kind")
        if source_kind == "youtube":
            from live_sources import canonical_youtube_live_url
            source = canonical_youtube_live_url(str(source))
        elif source_kind == "public_live":
            from public_cameras import get_camera
            # Fail fast if the requested camera ID is not in our reviewed catalog.
            get_camera(str(source))
        self._holds_live_slot = False
        if source_kind in {"youtube", "public_live"}:
            if not LIVE_STREAM_SLOTS.acquire(blocking=False):
                raise RuntimeError("One public live analysis is already using this shared server. Stop that session or try again later.")
            self._holds_live_slot = True
        self.source = source
        self.source_kind = source_kind
        self.is_live = isinstance(source, int) or source_kind in {"youtube", "public_live"}
        self.settings = settings
        self.label = label[:120]
        self.is_camera = isinstance(source, int)
        self.id = uuid.uuid4().hex[:12]
        self.folder = OUTPUTS / self.id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.summary_file = self.folder / "frames.csv"
        self.objects_file = self.folder / "objects.csv"
        self.video_file = self.folder / "annotated.mp4"
        self.raw_video_file = self.folder / "annotated_raw.mp4"
        self.video_export_error = None
        self.video_ready = False
        self.evidence = EvidenceAccumulator()
        self.crossings = CrossingCounter(settings.count_line_fraction)
        self.reference_frame_file = self.folder / "reference.jpg"
        self.frame_width = 0
        self.frame_height = 0
        self.events_file = self.folder / "events.csv"
        self.crossings_file = self.folder / "crossings.csv"
        self._stop = threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self.status = "starting"
        self.error = ""
        self.preview_jpeg: bytes | None = None
        self.best_preview_jpeg: bytes | None = None
        self.best_preview_at = 0.0
        self.best_detection_count = 0
        self.detected_class_totals = Counter()
        self.detected_frames = 0
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
        self.inference_ms_avg = 0.0
        self.empty_detection_frames = 0
        self.detection_confidence_sum = 0.0
        self.detection_count = 0
        self.detail_scans_attempted = 0
        self.detail_candidate_boxes = 0
        self.actual_source_fps = 0.0
        self.effective_sample_fps = 0.0
        self.scene = {}
        self.recent_events: deque[dict] = deque(maxlen=100)
        self.total_events = 0
        self.motion_samples = 0
        self.mean_apparent_speed = 0.0
        self.mean_calibrated_speed = 0.0
        self.calibrated_speed_samples = 0
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
                "video_ready": self.video_ready, "video_export_error": self.video_export_error,
                "evidence": self.evidence.snapshot(), "settings_fps": self.settings.analysis_fps,
                "crossings": self.crossings.snapshot(),
                "frame_width": self.frame_width, "frame_height": self.frame_height,
                "camera_fov_deg": self.settings.camera_fov_deg,
                "calibration": ({"points": self.settings.road_calibration.points,
                                "width_m": self.settings.road_calibration.width_m,
                                "length_m": self.settings.road_calibration.length_m}
                                if self.settings.road_calibration else None),
                "preview_jpeg": self.preview_jpeg, "best_preview_jpeg": self.best_preview_jpeg,
                "best_preview_at": self.best_preview_at, "best_detection_count": self.best_detection_count,
                "detected_class_totals": dict(self.detected_class_totals),
                "detected_frames": self.detected_frames, "source_kind": self.source_kind,
                "is_live": self.is_live, "duration_seconds": self.duration_seconds,
                "video_second": self.video_second, "total_frames": self.total_frames,
                "frames_read": self.frames_read, "analyzed_frames": self.analyzed_frames,
                "detected_now": dict(self.detected_now), "max_vehicles": self.max_vehicles,
                "max_people": self.max_people, "unique_tracks": len(self.unique_track_ids),
                "recent_frames": list(self.recent_frames), "recent_objects": list(self.recent_objects),
                "processing_fps": self.processing_fps, "device": self.device,
                "inference_ms_avg": round(self.inference_ms_avg,1),
                "empty_detection_frames": self.empty_detection_frames,
                "detail_scans_attempted": self.detail_scans_attempted,
                "additional_detail_candidate_boxes": self.detail_candidate_boxes,
                "average_detection_confidence": round(self.detection_confidence_sum/self.detection_count,3) if self.detection_count else None,
                "source_video_fps": self.actual_source_fps,
                "effective_sample_fps": self.effective_sample_fps,
                "requested_sample_fps": self.settings.analysis_fps,
                "model_name": self.settings.model_name,
                "detection_roi": self.settings.roi_rect,
                "inference_backend": getattr(self, "inference_backend", "PyTorch"),
                "scene": dict(self.scene), "recent_events": list(self.recent_events),
                "total_events": self.total_events, "mean_apparent_speed": self.mean_apparent_speed,
                "mean_calibrated_speed": self.mean_calibrated_speed,
                "calibrated_speed_samples": self.calibrated_speed_samples,
                "calibrated": self.settings.meters_per_pixel is not None,
                "paused": self._pause.is_set(), "is_camera": self.is_camera,
                "folder": str(self.folder), "finished_at": self.finished_at,
            }

    def _run(self):
        cap = None
        writer = None
        camera_reader = None
        try:
            # Resolve public live access BEFORE loading the heavyweight model:
            # inaccessible YouTube media should fail quickly and clearly.
            capture_source = self.source
            if self.source_kind in {"youtube", "public_live"}:
                with self._lock:
                    self.status = "connecting stream"
                if self.source_kind == "youtube":
                    from live_sources import resolve_youtube_live
                    capture_source, broadcast_title = resolve_youtube_live(self.source)
                else:
                    from public_cameras import get_camera
                    camera_info = get_camera(self.source)
                    capture_source = camera_info["stream_url"]
                    broadcast_title = camera_info["label"]
                with self._lock:
                    self.label = broadcast_title
            # Load model on the worker thread to avoid freezing UI.
            from model_runtime import load_detector
            import torch
            device = "0" if torch.cuda.is_available() else "cpu"
            if device == "cpu" and hasattr(torch, "set_num_threads"):
                # Avoid torch oversubscribing small shared CPU VMs.
                torch.set_num_threads(max(1,min(4,os.cpu_count() or 2)))
            with self._lock:
                self.device = "GPU (CUDA)" if device == "0" else "CPU"
                self.status = "loading model"
            model, self.inference_backend = load_detector(
                self.settings.model_name,self.settings.image_size,
                use_openvino=bool(self.settings.use_openvino and device=="cpu")
            )
            if self.source_kind in {"youtube", "public_live"}:
                from live_decoder import FFmpegLiveCapture
                cap = FFmpegLiveCapture(capture_source, fps=min(5, self.settings.analysis_fps))
                if not cap.isOpened():
                    raise RuntimeError(
                        "FFmpeg could not start decoding this YouTube video. "
                        "The source may require different transport or be unavailable from this server."
                    )
            else:
                cap = cv2.VideoCapture(capture_source)
                if not cap.isOpened():
                    raise ValueError("Cannot open video or camera. Check the local file path or camera permissions.")
            if self.is_live:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                reconnect_factory = None
                if self.source_kind in {"youtube", "public_live"}:
                    def reconnect_factory():
                        from live_decoder import FFmpegLiveCapture
                        if self.source_kind == "youtube":
                            from live_sources import resolve_youtube_live
                            renewed_url, _ = resolve_youtube_live(self.source)
                        else:
                            from public_cameras import get_camera
                            renewed_url = get_camera(self.source)["stream_url"]
                        return FFmpegLiveCapture(renewed_url, fps=min(5, self.settings.analysis_fps))
                camera_reader = LatestCameraFrames(cap, self._stop, reconnect_factory=reconnect_factory)
            video_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
            if not (1 <= video_fps <= 240):
                video_fps = 30.0
            total_frames = 0 if self.is_live else max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0))
            frame_step = max(1, round(video_fps / self.settings.analysis_fps)) if not self.is_live else 1
            with self._lock:
                self.actual_source_fps = round(video_fps,2)
                self.effective_sample_fps = round(video_fps/frame_step,2) if not self.is_live else min(5,self.settings.analysis_fps)
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
            # A blocked/live source should not spin indefinitely at zero frames.
            initial_frame_deadline = live_start + 30.0 if self.source_kind in {"youtube", "public_live"} else None
            previous_points: dict[int, tuple[float, float]] = {}
            road_tracker = RoadTracker(max_age=12)
            previous_motion: dict[int, tuple[float, float, float]] = {}
            previous_world: dict[int, tuple[float,float,float]] = {}
            last_emitted: dict[str, float] = {}
            with self.summary_file.open("w", encoding="utf-8-sig", newline="") as summaries, self.objects_file.open("w", encoding="utf-8-sig", newline="") as objects, self.events_file.open("w", encoding="utf-8-sig", newline="") as event_stream, self.crossings_file.open("w",encoding="utf-8-sig",newline="") as crossing_stream:
                summary_csv = csv.DictWriter(summaries, fieldnames=SUMMARY_FIELDS)
                object_csv = csv.DictWriter(objects, fieldnames=OBJECT_FIELDS)
                summary_csv.writeheader()
                object_csv.writeheader()
                event_csv = csv.DictWriter(event_stream, fieldnames=EVENT_FIELDS)
                event_csv.writeheader()
                crossing_csv=csv.DictWriter(crossing_stream,fieldnames=CROSSING_FIELDS)
                crossing_csv.writeheader()
                while not self._stop.is_set():
                    if self._pause.is_set():
                        time.sleep(0.12)
                        continue
                    # Grab rather than decode non-sampled frames, to reduce overhead.
                    if not self.is_live and i % frame_step:
                        if not cap.grab():
                            break
                        i += 1
                        continue
                    if self.is_live:
                        ok, frame, last_camera_version = camera_reader.next_frame(last_camera_version)
                        if not ok:
                            if initial_frame_deadline and time.monotonic() >= initial_frame_deadline:
                                raise RuntimeError(
                                    "No live video frames reached Smart Road within 30 seconds. "
                                    "The public camera may be offline, geo-restricted, or temporarily "
                                    "unavailable from this server. Try another free public camera "
                                    "or upload permitted road footage."
                                )
                            continue  # A slow/no frame interval, not necessarily a failure.
                        initial_frame_deadline = None
                    else:
                        ok, frame = cap.read()
                        if not ok:
                            break
                    frame_no = i
                    i += 1
                    seconds = (time.monotonic() - live_start) if self.is_live else frame_no / video_fps
                    if self.is_live and frame_no == 0:
                        live_start = time.monotonic()
                        seconds = 0.0
                    # Keep memory/inference reasonable for high-resolution video.
                    height, width = frame.shape[:2]
                    if width > 1600:
                        new_size = (1600, round(height * 1600 / width))
                        frame = cv2.resize(frame, new_size)
                    if self.frame_width == 0:
                        self.frame_width, self.frame_height = frame.shape[1], frame.shape[0]
                        cv2.imwrite(str(self.reference_frame_file),frame,[cv2.IMWRITE_JPEG_QUALITY,82])
                    roi_frame=frame
                    x_offset=y_offset=0
                    if self.settings.roi_rect is not None:
                        H,W=frame.shape[:2]
                        left,top,right,bottom=self.settings.roi_rect
                        x_offset=int(left*W)
                        y_offset=int(top*H)
                        roi_frame=frame[y_offset:max(y_offset+2,int(bottom*H)),
                                        x_offset:max(x_offset+2,int(right*W))]
                    started_inference = time.monotonic()
                    detail_interval=self.settings.detail_scan_every
                    detail_pass=(not self.is_live and detail_interval>0 and
                                 self.analyzed_frames%detail_interval==0)
                    observations, tracked, raw_detector = model_detections(
                        model, roi_frame,image_size=self.settings.image_size,
                        confidence=self.settings.confidence,class_ids=class_ids,
                        device=device,tracker=road_tracker,
                        detail_pass=detail_pass,
                        detail_side=self.analyzed_frames//max(1,detail_interval))
                    inference_ms = (time.monotonic()-started_inference)*1000
                    with self._lock:
                        self.detail_scans_attempted+=int(bool(getattr(road_tracker,"last_detail_attempt",False)))
                        self.detail_candidate_boxes+=int(getattr(road_tracker,"last_detail_added",0))
                    detections = []
                    apparent_speeds = []
                    calibrated_speeds = []
                    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    for observation in observations:
                            bounds = observation["bounds"]
                            confidence = observation["confidence"]
                            track_id = observation.get("track_id")
                            class_name = observation["cls"]
                            x1, y1, x2, y2 = [round(float(v), 1) for v in bounds]
                            # Tracker sees the crop, but all downstream data and
                            # the full original video remain in SOURCE coordinates.
                            x1+=x_offset; x2+=x_offset
                            y1+=y_offset; y2+=y_offset
                            center = ((x1 + x2) / 2, (y1 + y2) / 2)
                            direction = motion_direction(previous_points.get(track_id), center) if track_id is not None else "untracked"
                            image_px_s, calibrated_kmh = (None, None)
                            world_x, world_y, heading = None, None, None
                            calibration = self.settings.road_calibration
                            foot = ((x1+x2)/2, y2)
                            current_world = calibration.world(foot[0],foot[1],frame.shape[1],frame.shape[0]) if calibration else None
                            if current_world is not None:
                                world_x,world_y = (round(current_world[0],3),round(current_world[1],3))
                            if track_id is not None:
                                image_px_s, calibrated_kmh = image_motion(previous_motion.get(track_id), foot, seconds, self.settings.meters_per_pixel)
                                if current_world is not None:
                                    calibrated_speed, heading = ground_kinematics(
                                        previous_world.get(track_id),current_world,seconds
                                    )
                                    calibrated_kmh = calibrated_speed
                                    previous_world[track_id] = (current_world[0],current_world[1],seconds)
                                previous_points[track_id] = center
                                previous_motion[track_id] = (foot[0], foot[1], seconds)
                            if image_px_s is not None:
                                apparent_speeds.append(image_px_s)
                            if calibrated_kmh is not None and class_name in VEHICLES:
                                calibrated_speeds.append(calibrated_kmh)
                            detections.append({
                                "video_second": round(seconds, 2), "frame_number": frame_no,
                                "track_id": "" if track_id is None else int(track_id),
                                "class": class_name, "confidence": round(float(confidence), 3),
                                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                                "center_x": round(center[0], 1), "center_y": round(center[1], 1),
                                "direction": direction, "image_motion_px_s": image_px_s,
                                "calibrated_speed_kmh": calibrated_kmh,
                                "world_x_m": world_x, "world_y_m": world_y,
                                "heading_deg": heading, "observed_at_utc": now_iso,
                            })
                    counts = frame_counts(detections)
                    with self._lock:
                        crossing_events = self.crossings.observe(detections, frame.shape[1],frame.shape[0],seconds)
                    crossing_csv.writerows(crossing_events)
                    diag = scene_diagnostics(frame, detections, counts)
                    new_events = diagnostic_events(diag, seconds, last_emitted)
                    event_csv.writerows(new_events)
                    entry = {"video_second": round(seconds, 2), "frame_number": frame_no, **counts}
                    summary_csv.writerow(entry)
                    object_csv.writerows(detections)
                    if frame_no % 60 == 0:
                        summaries.flush()
                        objects.flush()
                        event_stream.flush()
                        crossing_stream.flush()
                    # Prune positions of inactive tracks, without resetting unique-ID count.
                    active_ids = {int(d["track_id"]) for d in detections if d["track_id"] != ""}
                    for track_id in list(previous_points):
                        if track_id not in active_ids:
                            del previous_points[track_id]
                            previous_motion.pop(track_id, None)
                    for track_id in list(previous_world):
                        if track_id not in active_ids: previous_world.pop(track_id,None)
                    annotated = draw_scene_overlay(frame, detections)
                    yline = int(self.settings.count_line_fraction * frame.shape[0])
                    cv2.line(annotated,(0,yline),(frame.shape[1]-1,yline),(90,211,255),2,cv2.LINE_AA)
                    cv2.putText(annotated,f"PASSED: {self.crossings.snapshot()['total_passed']}",
                                (12,max(18,yline-9)),cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2,cv2.LINE_AA)
                    if self.settings.save_video and not self.is_live:
                        if writer is None:
                            h, w = annotated.shape[:2]
                            output_rate = video_fps / frame_step
                            writer = cv2.VideoWriter(str(self.raw_video_file), cv2.VideoWriter_fourcc(*"mp4v"), output_rate, (w, h))
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
                        self.empty_detection_frames += not bool(detections)
                        self.detection_confidence_sum += sum(d["confidence"] for d in detections)
                        self.detection_count += len(detections)
                        self.inference_ms_avg = (
                            (self.inference_ms_avg * self.analyzed_frames + inference_ms)
                            / (self.analyzed_frames + 1)
                        )
                        self.preview_jpeg = buffer.tobytes() if encoded_ok else None
                        if counts["all_objects"] > self.best_detection_count and encoded_ok:
                            self.best_detection_count = counts["all_objects"]
                            self.best_preview_jpeg = buffer.tobytes()
                            self.best_preview_at = seconds
                        if counts["all_objects"]:
                            self.detected_frames += 1
                        self.detected_class_totals.update(d["class"] for d in detections)
                        self.frames_read = i
                        self.analyzed_frames += 1
                        self.video_second = seconds
                        self.detected_now = counts
                        self.scene = {k: v for k, v in diag.items() if k != "proximity_pairs"}
                        self.total_events += len(new_events)
                        self.recent_events.extend(new_events)
                        if apparent_speeds:
                            samples = len(apparent_speeds)
                            self.mean_apparent_speed = (self.mean_apparent_speed * self.motion_samples + sum(apparent_speeds)) / (self.motion_samples + samples)
                            self.motion_samples += samples
                        if calibrated_speeds:
                            samples = len(calibrated_speeds)
                            self.mean_calibrated_speed = (self.mean_calibrated_speed * self.calibrated_speed_samples + sum(calibrated_speeds)) / (self.calibrated_speed_samples + samples)
                            self.calibrated_speed_samples += samples
                        self.max_vehicles = max(self.max_vehicles, counts["vehicles"])
                        self.max_people = max(self.max_people, counts["people"])
                        self.unique_track_ids.update(active_ids)
                        self.recent_frames.append(entry)
                        self.recent_objects.extend(detections[-30:])
                        self.evidence.observe(
                            detections, counts, diag,
                            second=seconds, frame_width=frame.shape[1],
                            frame_height=frame.shape[0], events=new_events
                        )
                        self.processing_fps = (len(times) - 1) / elapsed if elapsed > 0 else 0
            with self._lock:
                self.status = (
                    "finalizing video" if writer is not None else
                    ("stopped" if self._stop.is_set() else ("ended" if self.is_live else "completed"))
                )
        except Exception as exc:
            with self._lock:
                self.error = f"{type(exc).__name__}: {exc}"
                self.status = "error"
        finally:
            user_cancelled = self._stop.is_set()
            self._stop.set()  # Ensure camera reader can leave its loop.
            if camera_reader is not None:
                camera_reader.close()
            if writer is not None:
                writer.release()
                # Convert OpenCV MP4V (not reliably supported in browsers) to
                # web-playable H264 on the server, without buffering video in RAM.
                if self.raw_video_file.is_file() and self.raw_video_file.stat().st_size > 0:
                    try:
                        ffmpeg = shutil.which("ffmpeg")
                        if ffmpeg is None:
                            raise RuntimeError("FFmpeg is not installed; cannot encode browser-playable H264.")
                        transcoded = subprocess.run([
                            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", str(self.raw_video_file), "-an",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                            "-threads", "2", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(self.video_file),
                        ], capture_output=True, timeout=240)
                        if transcoded.returncode != 0 or not self.video_file.is_file() or self.video_file.stat().st_size == 0:
                            raise RuntimeError("Could not encode H264 playback video on this server.")
                        self.video_ready = True
                    except (OSError, RuntimeError, subprocess.TimeoutExpired) as export_exc:
                        self.video_export_error = str(export_exc)[:220]
                        self.video_file.unlink(missing_ok=True)
                    finally:
                        self.raw_video_file.unlink(missing_ok=True)
                with self._lock:
                    if self.status == "finalizing video":
                        self.status = "stopped" if user_cancelled else (
                            "ended" if self.is_live else "completed"
                        )
            if cap is not None:
                cap.release()
            if self._holds_live_slot:
                self._holds_live_slot = False
                LIVE_STREAM_SLOTS.release()
            with self._lock:
                self.finished_at = time.time()
