"""Conservative image-only roadway perspective cues.

These are pixel-line hypotheses, NOT measured road boundaries, lane counts,
road type, curvature, or 3D depth. They help a reviewer pick ground reference
points on a clear fixed-camera frame without claiming semantic certainty.
"""
from __future__ import annotations

from math import atan2,degrees,hypot
import cv2
import numpy as np


def suggest_perspective(image_bgr, max_lines=36):
    if image_bgr is None or image_bgr.ndim!=3:
        raise ValueError("A decoded color camera frame is required.")
    height,width=image_bgr.shape[:2]
    if height<80 or width<100:
        raise ValueError("Source frame too small for perspective inspection.")
    scaled=cv2.resize(image_bgr,(min(width,960),int(height*min(width,960)/width)),
                      interpolation=cv2.INTER_AREA)
    h,w=scaled.shape[:2]
    y0=int(.12*h)
    gray=cv2.cvtColor(scaled,cv2.COLOR_BGR2GRAY)
    clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(gray)
    edges=cv2.Canny(cv2.GaussianBlur(clahe,(5,5),0),55,155)
    edges[:y0,:]=0
    minimum=max(32,round(.08*w))
    found=cv2.HoughLinesP(edges,rho=1,theta=np.pi/180,threshold=max(30,int(w*.05)),
                          minLineLength=minimum,maxLineGap=max(8,int(w*.027)))
    lines=[]
    for seg in ([] if found is None else found.reshape(-1,4).tolist()):
        x1,y1,x2,y2=map(int,seg)
        if hypot(x2-x1,y2-y1)<minimum:
            continue
        angle=abs(degrees(atan2(y2-y1,x2-x1)))
        if angle<16 or angle>164:
            continue
        # Restrict to geometry in the road-lower section; buildings and poles
        # are still possible — no semantic line label is assigned.
        if max(y1,y2)<.38*h:
            continue
        lines.append((x1,y1,x2,y2))
    lines.sort(key=lambda a:-hypot(a[2]-a[0],a[3]-a[1]))
    lines=lines[:max_lines]
    votes=[]
    for i,first in enumerate(lines):
        ax,ay,bx,by=first
        d1x,d1y=bx-ax,by-ay
        for second in lines[i+1:]:
            cx,cy,dx,dy=second
            d2x,d2y=dx-cx,dy-cy
            den=d1x*d2y-d1y*d2x
            if abs(den)<.08*hypot(d1x,d1y)*hypot(d2x,d2y):
                continue
            qx,qy=cx-ax,cy-ay
            t=(qx*d2y-qy*d2x)/den
            x,y=ax+t*d1x,ay+t*d1y
            if -.2*w<=x<=1.2*w and -.25*h<=y<=.78*h:
                votes.append((float(x),float(y)))
    inferred=None
    if len(votes)>=6:
        mx,my=np.median(np.asarray(votes),axis=0)
        scatter=float(np.median(np.linalg.norm(np.asarray(votes)-[mx,my],axis=1)))
        if scatter<max(w,h)*.14:
            inferred={"x_fraction":round(float(mx/w),3),
                      "y_fraction":round(float(my/h),3),
                      "scatter_px":round(scatter*width/w,1),
                      "candidate_intersections":len(votes)}
    return {
        "status":"perspective_hypothesis" if inferred else "insufficient_geometry",
        "source_dimensions":[width,height],
        "line_candidates":[[
            round(x1/w,4),round(y1/h,4),round(x2/w,4),round(y2/h,4)
        ] for x1,y1,x2,y2 in lines],
        "vanishing_point_candidate":inferred,
        "notes":"High-contrast line segments from original camera pixels; "
                "can include poles, shadows and road edges. No semantic "
                "lane identification, scale, road curvature or calibrated depth.",
    }


def draw_perspective_hints(image_bgr,hints):
    annotated=image_bgr.copy()
    h,w=annotated.shape[:2]
    for x1,y1,x2,y2 in hints["line_candidates"]:
        cv2.line(annotated,(round(x1*w),round(y1*h)),
                 (round(x2*w),round(y2*h)),(246,171,42),2,cv2.LINE_AA)
    point=hints["vanishing_point_candidate"]
    if point:
        x=int(point["x_fraction"]*w);y=int(point["y_fraction"]*h)
        cv2.circle(annotated,(x,y),9,(26,214,252),2,cv2.LINE_AA)
        cv2.putText(annotated,"Perspective hypothesis",(max(0,x-60),max(18,y-12)),
                    cv2.FONT_HERSHEY_SIMPLEX,.55,(26,214,252),2,cv2.LINE_AA)
    return cv2.cvtColor(annotated,cv2.COLOR_BGR2RGB)
