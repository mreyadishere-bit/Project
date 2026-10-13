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
    """Bounded approximate IDs; does not alter detections or claim identity certainty."""
    def __init__(self,max_age=12,minimum_iou=.06):
        self.max_age=max_age
        self.minimum_iou=minimum_iou
        self.states={}
        self.frame=0
        self.next_id=1

    def update(self,detections,shape):
        """Input dicts: bounds=[x1,y1,x2,y2], cls=string, confidence."""
        self.frame+=1
        height,width=shape[:2]
        for key in list(self.states):
            if self.frame-self.states[key]["frame"]>self.max_age:
                self.states.pop(key,None)
        proposals=[]
        for j,d in enumerate(detections):
            bbox=d["bounds"]
            x=(bbox[0]+bbox[2])/2
            y=bbox[3] # road-plane contact better than box centre
            w=max(1,bbox[2]-bbox[0])
            h=max(1,bbox[3]-bbox[1])
            for ident,state in self.states.items():
                if d["cls"]!=state["cls"]:continue
                prev=state["bounds"]
                age=max(1,self.frame-state["frame"])
                v=state["velocity"]
                px=(prev[0]+prev[2])/2+v[0]*age
                py=prev[3]+v[1]*age
                norm=max(20,w,h,prev[2]-prev[0],prev[3]-prev[1])
                delta=hypot((x-px)/norm,(y-py)/norm)
                overlap=iou(bbox,prev)
                # Admit large motion for near-camera cars; don't associate
                # opposite side of a divided road (diagonal cap).
                if delta>max(.95,1.2*age**.5) and overlap<self.minimum_iou:continue
                score=overlap*.64+.36/(1+delta)-.008*(age-1)
                proposals.append((score,j,ident))
        proposals.sort(reverse=True)
        used_d=set();used_t=set()
        mapping={}
        for score,j,ident in proposals:
            if j in used_d or ident in used_t:continue
            if score<.125:continue
            mapping[j]=ident
            used_d.add(j);used_t.add(ident)
        out=[]
        for j,d in enumerate(detections):
            ident=mapping.get(j)
            bbox=d["bounds"]
            if ident is None:
                ident=self.next_id
                self.next_id+=1
                vel=(0.,0.)
            else:
                old=self.states[ident]
                old_box=old["bounds"]
                age=max(1,self.frame-old["frame"])
                vel=(((bbox[0]+bbox[2]-old_box[0]-old_box[2])/2)/age,
                     (bbox[3]-old_box[3])/age)
            self.states[ident]={"bounds":tuple(bbox),"cls":d["cls"],
                                "frame":self.frame,"velocity":vel}
            out.append({**d,"track_id":ident})
        return out


def model_detections(model,frame,*,image_size,confidence,class_ids,device,tracker=None):
    """Prefer raw predictions, never silently drop detections for absent IDs."""
    if callable(getattr(model,"predict",None)):
        result=model.predict(frame,imgsz=image_size,conf=confidence,classes=class_ids,
                             device=device,verbose=False)[0]
        raw=True
    else:
        # Compatibility for offline model stubs and alternative trackers.
        result=model.track(frame,persist=True,tracker="bytetrack.yaml",
                           imgsz=image_size,conf=confidence,classes=class_ids,
                           device=device,verbose=False)[0]
        raw=False
    boxes=getattr(result,"boxes",None)
    if boxes is None or not len(boxes):
        return [],result,raw
    xyxy=boxes.xyxy.cpu().tolist()
    scores=boxes.conf.cpu().tolist()
    classes=boxes.cls.int().cpu().tolist()
    ids=(boxes.id.int().cpu().tolist() if not raw and getattr(boxes,"id",None) is not None
         else [None]*len(xyxy))
    data=[]
    names=getattr(result,"names",getattr(model,"names",{}))
    for box,score,cls,ident in zip(xyxy,scores,classes,ids):
        name=names[int(cls)] if isinstance(names,dict) else names[int(cls)]
        data.append({"bounds":tuple(float(x) for x in box),"cls":name,
                     "confidence":float(score),"track_id":ident})
    if raw:
        return tracker.update(data,frame.shape) if tracker is not None else data,result,raw
    # Stub/legacy backend returned IDs; keep all YOLO boxes even if ID absent.
    return data,result,raw
