"""Make real-browser, synthetic known-camera measured-road 3D fixture."""
from __future__ import annotations

import base64
import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from math import radians,tan

import cv2
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from calibrated_scene_view import HTML
from reconstruction import build_scene
from traffic_control_sim import ControlInputs,simulate


def build_fixture(target):
    root=Path(target).parent
    root.mkdir(parents=True,exist_ok=True)
    w,h=960,540
    frame=np.full((h,w,3),(95,123,138),np.uint8)
    cv2.line(frame,(140,h-2),(465,130),(244,228,196),8,cv2.LINE_AA)
    cv2.line(frame,(815,h-2),(518,130),(244,228,196),8,cv2.LINE_AA)
    source=root/"survey-original.jpg"
    cv2.imwrite(str(source),frame,[cv2.IMWRITE_JPEG_QUALITY,88])
    F=w/(2*tan(radians(70)/2))
    K=np.array([[F,0,w/2],[0,F,h/2],[0,0,1]],np.float64)
    r=np.array([.08,-.04,.05]);t=np.array([-3,-12,85.],np.float64)
    rect=np.array([[0,0,0],[8,0,0],[8,25,0],[0,25,0]],np.float64)
    corners,_=cv2.projectPoints(rect,r,t,K,None)
    points=[(float(x)/w,float(y)/h) for x,y in corners.reshape(-1,2)]
    file=root/"tracked-objects.csv"
    fields=["video_second","frame_number","class","track_id","confidence",
            "x1","y1","x2","y2","center_x","world_x_m","world_y_m"]
    with file.open("w",newline="",encoding="utf-8") as handle:
        output=csv.DictWriter(handle,fieldnames=fields)
        output.writeheader()
        for k in range(45):
            second=k*.2
            world=np.array([[4.,4+1.8*second,0]],np.float64)
            projected,_=cv2.projectPoints(world,r,t,K,None)
            x,y=map(float,projected.reshape(-1))
            output.writerow({
                "video_second":second,"frame_number":k*5,
                "class":"car","track_id":"17","confidence":.94,
                "x1":x-16,"y1":y-21,"x2":x+16,"y2":y,
                "center_x":x,"world_x_m":"","world_y_m":""
            })
    job=SimpleNamespace(objects_file=file,reference_frame_file=source)
    scene=build_scene(job,{
        "frame_width":w,"frame_height":h,"video_second":9.,
        "calibration":{"points":points,"width_m":8.,"length_m":25.},
        "camera_fov_deg":70
    },include_annotated_video=False)
    assert scene["metric_scene"] is not None
    assert any(len(p)>=7 for track in scene["tracks"] for p in track["points"])
    # Browser fixture must include the same optional concept payload created
    # by the actual Streamlit show_surveyed_scene route, not bypass it.
    scene["control_scenario"]=simulate(ControlInputs(
        seconds=120,lanes=2,vehicles_per_hour=480,pedestrians_per_hour=180))
    html=HTML.replace("__VIDEO__","").replace("__DATA__",
                  json.dumps(scene,separators=(",",":")).replace("</","<\\/"))
    Path(target).write_text(html,encoding="utf-8")
    print(f"Wrote surveyed camera fixture {target}, RMSE={scene['metric_scene']['reprojection_rmse_px']} px")


if __name__=="__main__":
    build_fixture(sys.argv[1])
