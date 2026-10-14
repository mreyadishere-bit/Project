"""Conservative, source-video-specific road observations for a useful review.

No generic road geometry, made-up crosswalk, fake stopped car, inferred
traffic offence, or automatic 3D claim. Camera position in IMAGE fractions
and original timestamps are the only grounded location evidence here.
"""
from __future__ import annotations
from collections import defaultdict
import csv
from math import hypot, isfinite
from pathlib import Path

MOTOR_CLASSES={"car","bus","truck","motorcycle"}
MAX_TRACKS=15000


def stationary_review_candidates(objects_file, frame_width,frame_height, *,
                                 min_seconds=3.0,min_samples=6,max_events=5):
    """Locate visibly nearly stationary motor-vehicle tracks; no parking claims.

    Only valid on a fixed camera. Low pixel motion is NOT zero road speed.
    """
    path=Path(objects_file) if objects_file else None
    w,h=int(frame_width or 0),int(frame_height or 0)
    if not path or not path.is_file() or w<2 or h<2:
        return []
    episodes=[]
    states={}
    def finish(key,state):
        if state["n"]<min_samples or state["last_t"]-state["start_t"]<min_seconds:
            return
        displacement=hypot(state["last_x"]-state["start_x"],state["last_y"]-state["start_y"])
        if displacement>.017 or state["max_spread"]>.026:
            return
        episodes.append({
          "kind":"low_image_motion_vehicle","title":"Check a vehicle appearing stationary",
          "video_second":round((state["start_t"]+state["last_t"])/2,2),
          "start_second":round(state["start_t"],2),
          "end_second":round(state["last_t"],2),
          "image_location":[round(state["last_x"],4),round(state["last_y"],4)],
          "frame_count":state["n"],"class":key[0],"track_id":key[1],
          "explanation":(
            f"A {key[0]} remained at nearly the same camera-image location for "
            f"{state['last_t']-state['start_t']:.1f} seconds. This is NOT proof of "
            "illegal parking, an obstruction, or a stopped vehicle in physical coordinates."
          ),
          "review_action":(
            "Inspect this moment for curbside pickup, queuing, vehicle access or "
            "an obstruction. If independently confirmed, consider a loading area, "
            "parking management or clearer stopping rules appropriate to the site."
          ),
          "limitations":"Fixed-camera image-motion screening only; verify the actual location and road rules.",
        })
    with path.open(encoding="utf-8-sig",newline="") as source:
        for row in csv.DictReader(source):
            kind=row.get("class","")
            ident=str(row.get("track_id","")).strip()
            if kind not in MOTOR_CLASSES or ident in ("","-1","None","nan"):
                continue
            try:
                t=float(row["video_second"])
                x=(float(row["x1"])+float(row["x2"]))/(2*w)
                y=float(row["y2"])/h
                conf=float(row.get("confidence") or 0)
            except (ValueError,KeyError,TypeError,ZeroDivisionError):
                continue
            if not all(isfinite(v) for v in (x,y,t,conf)) or not (.05<x<.95 and .35<y<.98 and conf>=.28):
                continue
            key=(kind,ident)
            prev=states.get(key)
            if prev and (t<=prev["last_t"] or t-prev["last_t"]>1.2):
                finish(key,prev)
                states.pop(key,None)
                prev=None
            if prev is None:
                if len(states)>=MAX_TRACKS:
                    continue
                states[key]=dict(start_t=t,last_t=t,start_x=x,start_y=y,
                                 last_x=x,last_y=y,max_spread=0.,n=1)
            else:
                prev["n"]+=1
                prev["last_t"]=t
                prev["last_x"]=x;prev["last_y"]=y
                prev["max_spread"]=max(prev["max_spread"],
                                    hypot(x-prev["start_x"],y-prev["start_y"]))
    for key,state in states.items():
        finish(key,state)
    episodes.sort(key=lambda e:(-e["frame_count"],e["video_second"]))
    unique=[]
    for event in episodes:
        if any(abs(event["video_second"]-past["video_second"])<3.5 and
               hypot(event["image_location"][0]-past["image_location"][0],
                     event["image_location"][1]-past["image_location"][1])<.05
               for past in unique):
            continue
        unique.append(event)
        if len(unique)>=max_events:
            break
    return sorted(unique,key=lambda e:e["video_second"])


def review_moments(interactions,stationary,max_items=8):
    """Use actual source-timestamp and normalized pixel location; no fake 3D."""
    moments=[]
    for event in interactions:
        x,y=event.get("image_location",(None,None))
        if x is None or y is None:continue
        moments.append({
            "kind":"pedestrian_vehicle_image_overlap",
            "title":"Pedestrian and vehicle image tracks appear close",
            "video_second":float(event["video_second"]),
            "image_location":[float(x),float(y)],
            "supporting_frames":int(event["frame_count"]),
            "evidence":"Repeated tracked image-footpoint proximity; physical distance unknown.",
            "review_action":"Check whether walking routes and vehicle movements genuinely conflict here. If so, survey crossing demand and consider physical separation or a controlled crossing where appropriate.",
            "confidence":"Needs manual confirmation in real video",
        })
    for event in stationary:
        moments.append({
            "kind":event["kind"],"title":event["title"],
            "video_second":event["video_second"],
            "image_location":event["image_location"],
            "supporting_frames":event["frame_count"],
            "evidence":event["explanation"],
            "review_action":event["review_action"],
            "confidence":"Visual screening only; no illegal-stopping claim",
        })
    moments.sort(key=lambda e:(e["video_second"],e["kind"]))
    return moments[:max_items]
