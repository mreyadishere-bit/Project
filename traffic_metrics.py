"""Streaming per-vehicle kinematics from the full CSV, never just final frame.

Estimates are uncalibrated unless surveyed geometry was supplied; acceleration
is smoothed and rejected when jumps or frame intervals are unsuitable.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import csv
from math import hypot, isfinite


def summarize_tracks(csv_file, *, limit=10000):
    tracks={}
    rows_seen=0
    world_samples=0
    for row in csv.DictReader(open(csv_file,encoding="utf-8-sig",newline="")):
        rows_seen+=1
        identifier=row.get("track_id")
        if identifier in (None,""):continue
        key=(row.get("class","unknown"),str(identifier))
        if key not in tracks:
            if len(tracks)>=limit:continue
            tracks[key]={"class":key[0],"track_id":key[1],
                         "frames":0,"first_s":None,"last_s":None,
                         "pixel_motion_sum":0.,"pixel_motion_n":0,
                         "world_distance_m":0.,"speed_kmh_sum":0.,"speed_kmh_n":0,
                         "speed_kmh_max":0.,"heading_deg_last":None,
                         "max_observed_accel_mps2":None,
                         "_prev_speed":None,"_prev":None}
        a=tracks[key]
        try:t=float(row["video_second"])
        except (ValueError,TypeError,KeyError):continue
        a["frames"]+=1
        a["first_s"]=t if a["first_s"] is None else min(a["first_s"],t)
        a["last_s"]=t
        apparent=row.get("image_motion_px_s")
        if apparent not in ("",None):
            try:
                px=float(apparent)
                if 0<=px<50000:
                    a["pixel_motion_sum"]+=px;a["pixel_motion_n"]+=1
            except ValueError:pass
        x=row.get("world_x_m");y=row.get("world_y_m")
        if x in ("",None) or y in ("",None):continue
        try:pos=(float(x),float(y),t)
        except (ValueError,TypeError):continue
        if not all(isfinite(n) for n in pos):continue
        old=a["_prev"]
        a["_prev"]=pos
        if old is None or t<=old[2]:continue
        dt=t-old[2]
        distance=hypot(pos[0]-old[0],pos[1]-old[1])
        speed=distance/dt*3.6
        # Discard identity jumps. These are not vehicle dynamics.
        if speed>180 or dt>3:continue
        a["world_distance_m"]+=distance
        a["speed_kmh_sum"]+=speed
        a["speed_kmh_max"]=max(a["speed_kmh_max"],speed)
        a["speed_kmh_n"]+=1;world_samples+=1
        try:a["heading_deg_last"]=float(row["heading_deg"]) if row.get("heading_deg") else a["heading_deg_last"]
        except ValueError:pass
        if a["_prev_speed"] is not None:
            last_speed,last_time=a["_prev_speed"]
            if .1<=t-last_time<=3:
                acceleration=abs((speed-last_speed)/3.6/(t-last_time))
                if acceleration<=15:
                    a["max_observed_accel_mps2"]=round(max(a["max_observed_accel_mps2"] or 0,acceleration),2)
        a["_prev_speed"]=(speed,t)
    results=[]
    for a in tracks.values():
        out={k:v for k,v in a.items() if not k.startswith("_") and not k.endswith("_sum") and not k.endswith("_n")}
        out["observed_seconds"]=round(max(0,a["last_s"]-a["first_s"]),2)
        out["mean_image_motion_px_s"]=round(a["pixel_motion_sum"]/a["pixel_motion_n"],2) if a["pixel_motion_n"] else None
        out["mean_surveyed_speed_kmh"]=round(a["speed_kmh_sum"]/a["speed_kmh_n"],2) if a["speed_kmh_n"] else None
        out["max_surveyed_speed_kmh"]=round(a["speed_kmh_max"],2) if a["speed_kmh_n"] else None
        out["world_distance_m"]=round(a["world_distance_m"],2) if a["speed_kmh_n"] else None
        results.append(out)
    return {"tracks":results,"rows":rows_seen,
            "surveyed_speed_samples":world_samples,
            "track_cap_reached":len(tracks)>=limit,
            "note":"Acceleration and speed are finite-difference estimates subject to calibration, jitter, frame sampling and ID switches; no vehicle mass is observed."}


def crossing_headways(events):
    """Intervals between distinct observed line crossings in same image direction."""
    d=defaultdict(list)
    for evt in events:
        d[evt["direction"]].append(float(evt["second"]))
    out={}
    for direction, times in d.items():
        times.sort()
        diffs=[round(b-a,2) for a,b in zip(times,times[1:]) if b>a]
        out[direction]={"observed_crossings":len(times),
                        "mean_gap_seconds":round(sum(diffs)/len(diffs),2) if diffs else None,
                        "min_gap_seconds":min(diffs) if diffs else None}
    return out
