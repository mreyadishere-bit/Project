"""Camera-specific stationary background for source-aligned 3D visualization.

Temporal median rejects objects that travel through the scene, while retaining
real road curvature, barriers, trees, lane geometry and original camera framing.
This is an IMAGE reference, not inferred metric 3D geometry.
"""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np


def background_photo(job, reference_data_url: str, width: int = 800, samples: int = 23) -> tuple[str, str]:
    output = Path(job.folder) / "scene_background.jpg"
    if output.is_file() and output.stat().st_size > 100:
        return "data:image/jpeg;base64," + base64.b64encode(output.read_bytes()).decode("ascii"), "Temporal median of source video frames"

    source = getattr(job, "source", None)
    if getattr(job, "source_kind", "file") != "file" or not isinstance(source, (str, Path)):
        return reference_data_url, "Single real reference frame (live source)"

    path = Path(source)
    if not path.is_file():
        return reference_data_url, "Single real reference frame (source unavailable)"

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return reference_data_url, "Single real reference frame (decoder unavailable)"
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count < 8:
            return reference_data_url, "Single real reference frame (short clip)"
        count = max(5, min(samples, frame_count // 2, 29))
        picks = np.linspace(0, frame_count - 1, count).astype(int)
        selected = []
        for frame_index in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            if h <= 0 or w <= 0:
                continue
            target_w = min(width, w)
            target_h = max(2, int(round(h * target_w / w)))
            resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
            selected.append(resized)
        if len(selected) < 5:
            return reference_data_url, "Single real reference frame (insufficient video samples)"
        # Median of stationary camera frames usually suppresses moving cars;
        # it cannot reconstruct permanently occluded objects or hidden areas.
        median = np.median(np.stack(selected, axis=0), axis=0).astype(np.uint8)
        ok, jpeg = cv2.imencode(".jpg", median, [cv2.IMWRITE_JPEG_QUALITY, 83])
        if not ok:
            return reference_data_url, "Single real reference frame (encode failure)"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(jpeg.tobytes())
        return "data:image/jpeg;base64," + base64.b64encode(jpeg.tobytes()).decode("ascii"), (
            f"Temporal median of {len(selected)} original frames (removes many moving vehicles)"
        )
    finally:
        cap.release()
