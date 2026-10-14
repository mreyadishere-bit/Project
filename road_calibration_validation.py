"""Independent surveyed camera-plane checkpoint validation.

Four calibration corners define a planar homography exactly. Their fit alone
cannot measure real-world accuracy. A separately surveyed fifth point tests
whether image-to-road measurements generalize inside the calibrated patch.
"""
from __future__ import annotations
from math import hypot, isfinite
from traffic_geometry import RoadCalibration


def validate_checkpoint(calibration: RoadCalibration, image_xy: tuple[float,float],
                        world_xy: tuple[float,float], width: int, height: int,
                        tolerance_m: float = 1.5) -> dict:
    if not 0.05 <= tolerance_m <= 10:
        raise ValueError("Checkpoint tolerance must be between 0.05 and 10 metres.")
    if len(image_xy)!=2 or len(world_xy)!=2:
        raise ValueError("Specify two image coordinates and two surveyed ground coordinates.")
    if not all(isfinite(float(v)) for v in (*image_xy,*world_xy)):
        raise ValueError("Finite coordinates are required.")
    if not all(0<=float(v)<=1 for v in image_xy):
        raise ValueError("Checkpoint image fractions must be within the video frame.")
    if any(hypot(float(image_xy[0])-px,float(image_xy[1])-py)<.025
           for px,py in calibration.points):
        raise ValueError("The fifth point must be independent of all four calibration corners.")
    x,y=world_xy
    if not (0<=x<=calibration.width_m and 0<=y<=calibration.length_m):
        raise ValueError("Checkpoint must be within the independently measured road patch.")
    projected=calibration.world(image_xy[0]*width,image_xy[1]*height,width,height)
    if projected is None:
        raise ValueError("Checkpoint lies outside the supported calibrated road plane.")
    error=hypot(projected[0]-x,projected[1]-y)
    return {
        "status":"independently_checked" if error<=tolerance_m else "failed_independent_check",
        "error_m":round(error,3),
        "tolerance_m":tolerance_m,
        "estimated_world_m":[round(projected[0],3),round(projected[1],3)],
        "surveyed_world_m":[round(x,3),round(y,3)],
        "scope":"One additional surveyed flat-road point only. This is not a full camera accuracy certification.",
    }
