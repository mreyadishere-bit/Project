"""Lightweight camera-friendly association independent from detector filtering.

Use YOLO predict() to keep every detected object, then associate IDs separately.
There is no extra neural-network inference, and missing IDs must never cause
the detector's visually present boxes to disappear.
"""
from __future__ import annotations

from math import hypot
from collections import defaultdict

def iou(a,b):
    l=max(a[0],b[0]);t=max(a[1],b[1]);r=min(a[2],b[2]);bot=min(a[3],b[3])
    inter=max(0,r-l)*max(0,bot-t)
    aa=max(0,a[2]-a[0])*max(0,a[3]-a[1])
    bb=max(0,b[2]-b[0])*max(0,b[3]-b[1])
    return inter/max(1e-6,aa+bb-inter)

class RoadTracker:
    """Motion-gated global association; raw YOLO boxes are never discarded.

    Global LAP matching avoids greedy local collisions in dense traffic.
    Prediction is image-plane-only, not a metric vehicle-identity guarantee.
    """
    def __init__(self,max_age=12,minimum_iou=.06):
        self.max_age=max_age
        self.minimum_iou=minimum_iou
        self.states={}
        self.frame=0
        self.next_id=1
        self.last_association="none"

    @staticmethod
    def _foot(box):
        return ((float(box[0])+float(box[2]))/2,float(box[3]))

    @staticmethod
    def _size(box):
        return (max(2.,float(box[2])-float(box[0])),
                max(2.,float(box[3])-float(box[1])))

    def update(self,detections,shape):
        """Input object dicts: bounds=(x1,y1,x2,y2), cls, confidence."""
        self.frame+=1
        # Only past viable tracks may receive the new detector observations.
        for key in list(self.states):
            if self.frame-self.states[key]["frame"]>self.max_age:
                self.states.pop(key,None)
        track_ids=list(self.states)
        n=len(track_ids);m=len(detections)
        proposals=[]
        if n and m:
            import numpy as np
            cost=np.full((n,m),1e6,np.float64)
            for i,ident in enumerate(track_ids):
                state=self.states[ident]
                old=state["bounds"]
                ox,oy=self._foot(old)
                old_w,old_h=self._size(old)
                age=max(1,self.frame-state["frame"])
                vx,vy=state["velocity"]
                px,py=ox+vx*age,oy+vy*age
                for j,d in enumerate(detections):
                    if d["cls"]!=state["cls"]:
                        continue
                    box=d["bounds"]
                    x,y=self._foot(box)
                    w,h=self._size(box)
                    # Preserve perspective sizing but penalize impossible
                    # sudden size changes / switches between nearby objects.
                    size_ratio=max(w/old_w,old_w/w,h/old_h,old_h/h)
                    if size_ratio>3.0:
                        continue
                    norm=max(14.,w,h,old_w,old_h)
                    predicted_delta=hypot((x-px)/norm,(y-py)/norm)
                    if predicted_delta>min(2.7,1.5+.18*(age-1)):
                        continue
                    box_iou=iou(box,old)
                    direction_cost=.23*predicted_delta
                    appearance_cost=.16*(1-box_iou)
                    scale_cost=.10*(size_ratio-1)
                    staleness=.025*(age-1)
                    cost[i,j]=direction_cost+appearance_cost+scale_cost+staleness
            try:
                import lap
                _,row_assign,_=lap.lapjv(cost,extend_cost=True,cost_limit=.82)
                proposals=[(j,track_ids[i]) for i,j in enumerate(row_assign)
                           if j>=0 and cost[i,j]<.82]
                self.last_association="global_lap"
            except (ImportError,RuntimeError,ValueError):
                # Still work in minimal offline environments with no lap,
                # but production declares lap in requirements.
                edges=sorted((cost[i,j],i,j) for i in range(n)
                             for j in range(m) if cost[i,j]<.82)
                used_i=set();used_j=set()
                for _,i,j in edges:
                    if i not in used_i and j not in used_j:
                        used_i.add(i);used_j.add(j)
                        proposals.append((j,track_ids[i]))
                self.last_association="greedy_fallback"
        else:
            self.last_association="no_matches"
        mapping=dict(proposals)
        out=[]
        for j,d in enumerate(detections):
            ident=mapping.get(j)
            box=tuple(map(float,d["bounds"]))
            if ident is None:
                ident=self.next_id
                self.next_id+=1
                vel=(0.,0.)
            else:
                previous=self.states[ident]
                age=max(1,self.frame-previous["frame"])
                x,y=self._foot(box)
                ox,oy=self._foot(previous["bounds"])
                dx,dy=(x-ox)/age,(y-oy)/age
                v=previous["velocity"]
                vel=(.65*dx+.35*v[0],.65*dy+.35*v[1])
            self.states[ident]={"bounds":box,"cls":d["cls"],
                                "frame":self.frame,"velocity":vel}
            out.append({**d,"track_id":ident})
        return out


def _extract_boxes(result, model, *, dx=0, dy=0):
    """Decode every YOLO detection into full-source-frame coordinates."""
    boxes=getattr(result,"boxes",None)
    if boxes is None or not len(boxes):
        return []
    xyxy=boxes.xyxy.cpu().tolist()
    confidences=boxes.conf.cpu().tolist()
    classes=boxes.cls.int().cpu().tolist()
    ids=(boxes.id.int().cpu().tolist()
         if getattr(boxes,"id",None) is not None else [None]*len(xyxy))
    names=getattr(result,"names",getattr(model,"names",{}))
    observed=[]
    for xy,score,cls,ident in zip(xyxy,confidences,classes,ids):
        name=names[int(cls)] if isinstance(names,dict) else names[int(cls)]
        observed.append({
            "bounds":(float(xy[0])+dx,float(xy[1])+dy,
                      float(xy[2])+dx,float(xy[3])+dy),
            "cls":name,"confidence":float(score),"track_id":ident
        })
    return observed


def _merge_multiscale(primary,detail,threshold=.44):
    """Keep the primary full-frame boxes and add class-consistent tile discoveries.

    Suppresses duplicate detections; never discards full-frame observations.
    """
    combined=list(primary)
    for candidate in sorted(detail,key=lambda d:-d["confidence"]):
        if any(old["cls"]==candidate["cls"]
               and iou(old["bounds"],candidate["bounds"])>=threshold
               for old in combined):
            continue
        combined.append(candidate)
    return combined


def model_detections(model,frame,*,image_size,confidence,class_ids,device,
                     tracker=None,detail_pass=False,detail_side=0):
    """Raw full-frame YOLO plus an optional low-duty high-detail crop pass.

    A crop is deliberately used infrequently on recordings to reduce
    small/distant vehicle undercount. It adds one inference pass, so the
    setting is not for latency-constrained live cameras. The detector always
    runs full-frame, and the extra pass cannot remove its detections.
    """
    if callable(getattr(model,"predict",None)):
        result=model.predict(frame,imgsz=image_size,conf=confidence,
                             classes=class_ids,device=device,verbose=False)[0]
        raw=True
    else:
        result=model.track(frame,persist=True,tracker="bytetrack.yaml",
                           imgsz=image_size,conf=confidence,classes=class_ids,
                           device=device,verbose=False)[0]
        raw=False
    data=_extract_boxes(result,model)
    if tracker is not None:
        tracker.last_detail_added=0
        tracker.last_detail_attempt=False
    if raw and detail_pass:
        height,width=frame.shape[:2]
        if height>=240 and width>=360:
            # Alternating overlapping left/right tiles increase the apparent
            # size of distant traffic; the next tile pass covers the other side.
            left=0 if detail_side%2==0 else int(width*.32)
            right=int(width*.68) if detail_side%2==0 else width
            bottom=max(2,int(height*.68))
            crop=frame[:bottom,left:right]
            if crop.shape[0]>=64 and crop.shape[1]>=120:
                try:
                    if tracker is not None:
                        tracker.last_detail_attempt=True
                    extra=model.predict(crop,imgsz=image_size,conf=confidence,
                                        classes=class_ids,device=device,verbose=False)[0]
                    discovered=_extract_boxes(extra,model,dx=left)
                    # Only boxes physically inside the cropped source region.
                    discovered=[d for d in discovered if
                        d["bounds"][2]>d["bounds"][0] and
                        d["bounds"][3]>d["bounds"][1] and
                        d["bounds"][0]>=left-2 and
                        d["bounds"][2]<=right+2 and
                        d["bounds"][1]>=-2 and
                        d["bounds"][3]<=bottom+2]
                    merged=_merge_multiscale(data,discovered)
                    if tracker is not None:
                        tracker.last_detail_added=len(merged)-len(data)
                    data=merged
                except (RuntimeError,ValueError,OSError,ImportError):
                    # Detail processing is a supplementary quality attempt.
                    # Full-frame observations remain valid if its tile fails.
                    pass
    if raw:
        return (tracker.update(data,frame.shape)
                if tracker is not None else data),result,raw
    return data,result,raw
