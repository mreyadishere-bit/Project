"""Approximate camera-pose-grounded reconstruction from a surveyed road rectangle.

Camera intrinsics inferred from a user-specified FOV, not recovered from video;
poses are only offered when reprojection error is acceptably low. The surface
texture comes from ONE source frame and does not contain true 3D buildings.
"""
from __future__ import annotations
import base64
from io import BytesIO
from math import radians,tan
import cv2
import numpy as np


def surveyed_road_scene(image_bgr, calibration, horizontal_fov_deg=70):
    height,width=image_bgr.shape[:2]
    if not 30<=horizontal_fov_deg<=120:
        raise ValueError("Camera horizontal FOV should be 30–120 degrees.")
    image_points=np.array([(x*width,y*height) for x,y in calibration.points],np.float64)
    road_w,road_l=float(calibration.width_m),float(calibration.length_m)
    world_pts=np.array([[0,0,0],[road_w,0,0],
                       [road_w,road_l,0],[0,road_l,0]],np.float64)
    focal=width/(2*tan(radians(horizontal_fov_deg)/2))
    K=np.array([[focal,0,width/2],[0,focal,height/2],[0,0,1]],np.float64)
    distort=np.zeros((4,1),np.float64)
    success,rvec,tvec=cv2.solvePnP(world_pts,image_points,K,distort,
                                   flags=cv2.SOLVEPNP_ITERATIVE)
    if not success:
        raise ValueError("Camera pose solution failed.")
    projected,_=cv2.projectPoints(world_pts,rvec,tvec,K,distort)
    err=float(np.sqrt(np.mean(np.sum((projected.reshape(-1,2)-image_points)**2,axis=1))))
    if not np.isfinite(err) or err>16:
        raise ValueError(f"Calibration reprojection error ({err:.1f} px) too high.")
    R,_=cv2.Rodrigues(rvec)
    out_size=(min(1280,max(300,round(road_w/road_l*900))),900)
    dst=np.array([[0,0],[out_size[0]-1,0],
                  [out_size[0]-1,out_size[1]-1],[0,out_size[1]-1]],np.float32)
    warp=cv2.getPerspectiveTransform(image_points.astype(np.float32),dst)
    road=cv2.warpPerspective(image_bgr,warp,out_size,flags=cv2.INTER_LINEAR)
    ok,jpg=cv2.imencode(".jpg",road,[cv2.IMWRITE_JPEG_QUALITY,80])
    if not ok: raise RuntimeError("Could not encode road texture.")
    return {
       "texture":"data:image/jpeg;base64,"+base64.b64encode(jpg.tobytes()).decode("ascii"),
       "width_m":road_w,"length_m":road_l,"fov_deg":float(horizontal_fov_deg),
       "rotation_cv":R.tolist(),"translation_cv":tvec.reshape(3).tolist(),
       "reprojection_rmse_px":round(err,2),
       "interpretation":"Surveyed flat road-plane patch, estimated camera intrinsics, generic 3D vehicles; NOT complete scene photogrammetry.",
    }
