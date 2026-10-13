"""Crossing-line traffic counts and optional surveyed planar road calibration.

Single camera 2D footage cannot yield a metric 3D scene without geometry.
Calibration is used for road-plane speeds and locations only, not object mass.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from math import atan2, degrees, hypot, isfinite
import cv2
import numpy as np

@dataclass(frozen=True)
class RoadCalibration:
    # Quadrilateral in SOURCE IMAGE fractions, ordered near-left, near-right,
    # far-right, far-left. Must be on the SAME FLAT road plane.
    points: tuple
    width_m: float
    length_m: float

    def __post_init__(self):
        if len(self.points)!=4 or any(len(p)!=2 for p in self.points):
            raise ValueError("Select exactly four road-plane reference corners.")
        if any(not (isfinite(float(v)) and 0<=float(v)<=1) for p in self.points for v in p):
            raise ValueError("Calibration fractions must be in [0,1].")
        if not (1<=self.width_m<=100 and 2<=self.length_m<=1000):
            raise ValueError("Surveyed road dimensions are outside supported range.")
        contour=np.array(self.points,np.float32)
        area=abs(cv2.contourArea(contour))
        if area < .0001 or not cv2.isContourConvex(contour):
            raise ValueError("Four road corners must form a non-degenerate convex quadrilateral.")
        if cv2.contourArea(contour)<0:
            # OpenCV area sign is orientation-dependent, and ignored here.
            pass

    def matrix(self):
        p=np.array(self.points,np.float32)
        target=np.array([[0,0],[self.width_m,0],
                         [self.width_m,self.length_m],[0,self.length_m]],np.float32)
        return cv2.getPerspectiveTransform(p,target)

    def world(self, x_px:float,y_px:float,w:int,h:int):
        if w<=0 or h<=0: return None
        xy=cv2.perspectiveTransform(
            np.array([[[x_px/w,y_px/h]]],np.float32),self.matrix())[0,0]
        if not np.isfinite(xy).all():return None
        if not (-.03*self.width_m <= xy[0] <= 1.03*self.width_m and
                -.03*self.length_m <= xy[1] <= 1.03*self.length_m):
            # Homography extrapolation outside the surveyed patch is not a
            # trustworthy measured road position.
            return None
        return (float(xy[0]),float(xy[1]))


def ground_kinematics(previous, world, timestamp, maximum_kmh=180):
    """World-plane displacement from consecutive same-ID footpoints.

    Speed and heading are estimates. Reject implausible jumps / identity swaps.
    """
    if previous is None or world is None:return None,None
    dx=world[0]-previous[0]
    dy=world[1]-previous[1]
    dt=timestamp-previous[2]
    if dt<=0:return None,None
    speed=3.6*hypot(dx,dy)/dt
    if speed>maximum_kmh:return None,None
    return round(speed,2),round(degrees(atan2(dy,dx)),1)


class CrossingCounter:
    """One count per stable track ID crossing the configurable horizontal line."""
    def __init__(self, y_fraction=.50, deadband=.012):
        if not (.05<=y_fraction<=.95):raise ValueError("Count line outside view.")
        self.y_fraction=y_fraction
        self.deadband=deadband
        self.previous={}
        self.counted=set()
        self.by_class=Counter()
        self.by_direction=Counter()
        self.events=[]
        self.untracked=0

    def observe(self, detections, width, height, time_s):
        found=[]
        if height<=0:return found
        for d in detections:
            ident=d.get("track_id")
            if ident in (None,""):
                self.untracked+=1
                continue
            ident=int(ident)
            cls=d["class"]
            if cls not in {"car","truck","bus","motorcycle","bicycle"}:continue
            y=float(d["y2"])/height
            side= -1 if y<self.y_fraction-self.deadband else (1 if y>self.y_fraction+self.deadband else 0)
            key=(cls,ident)
            old=self.previous.get(key)
            if side==0:continue
            if old is not None and old!=side and key not in self.counted:
                direction="toward camera (down)" if side==1 else "away from camera (up)"
                self.counted.add(key)
                self.by_class[cls]+=1
                self.by_direction[direction]+=1
                event={"second":round(time_s,2),"track_id":ident,"class":cls,
                       "direction":direction}
                found.append(event)
                self.events.append(event)
            self.previous[key]=side
        return found

    def snapshot(self):
        return {"line_y_fraction":self.y_fraction,"total_passed":sum(self.by_class.values()),
                "passed_by_class":dict(self.by_class),
                "passed_by_direction":dict(self.by_direction),
                "untracked_observations":self.untracked,
                "meaning":"Counted when a tracked footpoint crossed the line; objects that never reach the line are excluded. IDs can fragment during occlusion."}
