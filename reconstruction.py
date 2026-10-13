"""Export bounded, time-aligned tracked scene proxies for interactive 3D viewing.

A fixed source frame is used as a photo reference, not a reconstructed
photogrammetric environment. Observed 2D positions and time are retained.
"""
from __future__ import annotations
import base64
import csv
import json
from pathlib import Path


def build_scene(job, snapshot, max_points=30000, max_tracks=500, include_annotated_video=True):
    csvpath=Path(job.objects_file)
    reference=Path(getattr(job,"reference_frame_file",""))
    if not csvpath.is_file() or not reference.is_file():
        raise ValueError("No analyzed video / reference frame found. Run video analysis first.")
    w=int(snapshot.get("frame_width") or 0)
    h=int(snapshot.get("frame_height") or 0)
    if w<=0 or h<=0:
        raise ValueError("Video frame dimensions missing.")
    # Approximate rows per file based on size; sample evenly across the
    # entire CSV, rather than silently dropping the end of a long recording.
    stride=max(1,int(csvpath.stat().st_size / (max_points*175))+1)
    # A post-analysis survey overrides stale/incomplete world values from
    # the earlier uncalibrated processing run. No YOLO rerun is necessary.
    calibration=None
    if snapshot.get("calibration"):
        from traffic_geometry import RoadCalibration
        data=snapshot["calibration"]
        calibration=RoadCalibration(
            tuple(tuple(p) for p in data["points"]),
            float(data["width_m"]),float(data["length_m"]))
    tracks={}
    sampled=0
    ignored=0
    with csvpath.open(encoding="utf-8-sig",newline="") as source:
        for index,row in enumerate(csv.DictReader(source)):
            if index % stride:continue
            if row.get("track_id") in (None,""):continue
            key=str(row.get("class","unknown"))+"-"+str(row["track_id"])
            if key not in tracks and len(tracks)>=max_tracks:
                ignored+=1
                continue
            try:
                point=[round(float(row["video_second"]),3),
                       round(float(row["center_x"])/w,5),
                       round(float(row["y2"])/h,5),
                       round(float(row["x2"])-float(row["x1"]),1)/w,
                       round(float(row["y2"])-float(row["y1"]),1)/h]
                if not (0<=point[1]<=1 and -0.1<=point[2]<=1.1):continue
                if calibration is not None:
                    calibrated=calibration.world(
                        float(row["center_x"]),float(row["y2"]),w,h)
                    if calibrated is not None:
                        point.extend([round(calibrated[0],3),round(calibrated[1],3)])
                elif row.get("world_x_m") and row.get("world_y_m"):
                    point += [round(float(row["world_x_m"]),3),
                              round(float(row["world_y_m"]),3)]
            except (ValueError,TypeError,KeyError):
                continue
            entry=tracks.setdefault(key,{"class":row["class"],"id":row["track_id"],"points":[]})
            entry["points"].append(point)
            sampled+=1
    # Avoid passing huge asset to the browser. This file is a reference photo,
    # and its own vehicles are not removed or magically made into 3D.
    from PIL import Image
    from io import BytesIO
    im=Image.open(reference).convert("RGB")
    im.thumbnail((960,600))
    encoded=BytesIO()
    im.save(encoded,"JPEG",quality=65,optimize=True)
    metric=None
    cal=snapshot.get("calibration")
    if calibration is not None:
        import cv2
        from metric_scene import surveyed_road_scene
        source_bgr=cv2.imread(str(reference))
        if source_bgr is None:
            raise ValueError("Original calibration frame could not be decoded.")
        metric=surveyed_road_scene(source_bgr,calibration,
                                  float(snapshot.get("camera_fov_deg",70)))
    video_inline=None
    video=Path(getattr(job,"video_file",""))
    # Keep embedding capped so long recordings do not overload Streamlit
    # or browser memory. Do not create public URLs to user uploads.
    if include_annotated_video and getattr(job,"video_ready",False) and video.is_file() and 0<video.stat().st_size<=8*1024*1024:
        video_inline="data:video/mp4;base64,"+base64.b64encode(video.read_bytes()).decode("ascii")
    return {
        "embedded_video":video_inline,
        "metric_scene":metric,
        "source":"Observed YOLO track boxes + fixed real video frame",
        "image":"data:image/jpeg;base64,"+base64.b64encode(encoded.getvalue()).decode("ascii"),
        "width":w,"height":h,"duration":float(snapshot.get("video_second") or 1),
        "first_second":0,"tracks":list(tracks.values()),
        "line":snapshot.get("crossings",{}).get("line_y_fraction",.5),
        "calibration":snapshot.get("calibration"),
        "preview_observations":sampled,"sampling_stride":stride,
        "excluded_new_tracks":ignored,
        "note":"A source-frame photo reference and approximate generic 3D meshes, not a complete metric reconstruction. Occluded buildings, car shapes, mass and road geometry cannot be recovered from one image.",
    }
