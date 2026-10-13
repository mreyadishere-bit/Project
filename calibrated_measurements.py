"""Post-analysis calibrated ground-plane measurements from original YOLO tracks.

Only a user-surveyed, planar quadrilateral can unlock meters/km/h. A fixed
camera and ground-contact assumption are required. We never infer distance
from bounding-box scale, pixels/s or a guessed camera FOV.

This can run AFTER video processing: the expensive detector is not rerun.
"""
from __future__ import annotations

from collections import defaultdict, deque
import csv
from math import hypot, isfinite
from pathlib import Path
from statistics import median

from traffic_geometry import RoadCalibration

ROAD_USERS = {"car","truck","bus","motorcycle","bicycle","person"}
MAX_ACCEPTED_KMH = {"person":18., "bicycle":75., "motorcycle":180.,
                    "car":180., "bus":145., "truck":145.}


def calibrated_tracks(objects_path, calibration:RoadCalibration, width:int, height:int,
                      *, min_window_s=.5, max_gap_s=1.8, max_accel_mps2=9.,
                      min_support=4):
    """Scan tracked detections with bounded per-ID history and reject ID swaps.

    Returns summaries and sampled, surveyed world trajectories. Measurements
    are uncertain, particularly near horizon/occlusion and on sloping roads.
    """
    if width<=0 or height<=0:
        raise ValueError("Original source width/height are required.")
    filepath=Path(objects_path)
    if not filepath.is_file():
        raise ValueError("Tracking CSV missing; run analysis first.")
    history=defaultdict(lambda:deque(maxlen=12))
    measures=defaultdict(list)
    paths=defaultdict(list)
    ignored=defaultdict(int)
    rows=0
    with filepath.open(encoding="utf-8-sig",newline="") as handle:
        for record in csv.DictReader(handle):
            rows+=1
            ident=str(record.get("track_id","")).strip()
            kind=str(record.get("class","")).strip().lower()
            if ident in ("","-1","None","nan") or kind not in ROAD_USERS:
                ignored["untracked_or_other"]+=1
                continue
            try:
                timestamp=float(record["video_second"])
                confidence=float(record.get("confidence",0) or 0)
                foot_x=(float(record["x1"])+float(record["x2"]))/2
                foot_y=float(record["y2"])
            except (KeyError,ValueError,TypeError):
                ignored["invalid_record"]+=1
                continue
            if not all(isfinite(v) for v in (timestamp,confidence,foot_x,foot_y)):
                ignored["invalid_record"]+=1
                continue
            if confidence<.20:
                ignored["weak_detection"]+=1
                continue
            xy=calibration.world(foot_x,foot_y,width,height)
            if xy is None:
                ignored["outside_surveyed_plane"]+=1
                continue
            key=(kind,ident)
            h=history[key]
            if h and (timestamp<=h[-1][0] or timestamp-h[-1][0]>max_gap_s):
                h.clear()
            # Location jumps of a tracking ID should not become a speed spike.
            if h:
                dt=timestamp-h[-1][0]
                instantaneous_kmh=3.6*hypot(xy[0]-h[-1][1],xy[1]-h[-1][2])/dt
                if instantaneous_kmh>MAX_ACCEPTED_KMH[kind]*1.35:
                    ignored["track_discontinuity"]+=1
                    h.clear()
            paths[key].append((round(timestamp,3),round(xy[0],3),round(xy[1],3)))
            older=next((p for p in h if timestamp-p[0]>=min_window_s),None)
            if older is not None:
                dt=timestamp-older[0]
                kmh=3.6*hypot(xy[0]-older[1],xy[1]-older[2])/dt
                previous=measures[key][-1]["speed_kmh"] if measures[key] else None
                # Suppress track-ID switches and very unstable camera-footpoints.
                if (kmh<=MAX_ACCEPTED_KMH[kind] and
                    (previous is None or
                     abs(kmh-previous)/3.6/dt<=max_accel_mps2)):
                    measures[key].append({
                        "video_second":round(timestamp,2),
                        "speed_kmh":round(kmh,2),
                        "world_x_m":round(xy[0],3),
                        "world_y_m":round(xy[1],3),
                        "track_id":ident,"class":kind,
                    })
                else:
                    ignored["implausible_motion"]+=1
            h.append((timestamp,*xy))
    tracks=[]
    all_speeds=[]
    for (kind,ident),items in sorted(measures.items()):
        if len(items)<min_support:
            ignored["insufficient_track_support"]+=1
            continue
        speeds=[p["speed_kmh"] for p in items]
        med=median(speeds)
        all_speeds.extend(speeds)
        tracks.append({
            "class":kind,"track_id":ident,
            "accepted_samples":len(items),
            "median_speed_kmh":round(med,1),
            "min_speed_kmh":round(min(speeds),1),
            "max_speed_kmh":round(max(speeds),1),
            "first_second":items[0]["video_second"],
            "last_second":items[-1]["video_second"],
            "points":paths[(kind,ident)][::max(1,len(paths[(kind,ident)])//400)],
        })
    return {
        "status":"surveyed_planar_estimates",
        "tracks":tracks,
        "median_track_speed_kmh":round(median([t["median_speed_kmh"] for t in tracks]),1) if tracks else None,
        "rows_scanned":rows,
        "accepted_track_count":len(tracks),
        "rejected":dict(ignored),
        "basis":{
            "geometry":"Four surveyed, coplanar reference corners; ground-plane homography",
            "survey_width_m":calibration.width_m,
            "survey_length_m":calibration.length_m,
            "min_window_s":min_window_s,
            "min_support_samples":min_support,
            "note":"Approximate tracked-footpoint ground speeds, NOT certified radar speed. "
                   "Sensitive to perspective, frame rate, footpoint accuracy, "
                   "occlusion and vehicle contact location. Not applicable to "
                   "sloping roads or objects outside the calibrated patch.",
        },
    }
