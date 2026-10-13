"""Optional, explicitly surveyed camera calibration AFTER AI analysis.

Keep the normal upload-and-analyze flow zero-settings. A valid road rectangle
is never inferred from a filename or box detector. This module enables real
road-plane scale only after the reviewer identifies four points and supplies
surveyed dimensions of one flat road patch.
"""
from __future__ import annotations
import json
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from traffic_geometry import RoadCalibration
from calibrated_measurements import calibrated_tracks
from metric_scene import surveyed_road_scene


POINT_NAMES=("Near left","Near right","Far right","Far left")


def annotated_frame(image,points):
    out=image.copy()
    h,w=out.shape[:2]
    palette=[(59,136,248),(39,179,96),(218,137,62),(190,94,192)]
    positions=[]
    for i,(x,y) in enumerate(points):
        x,y=int(x*w),int(y*h)
        positions.append((x,y))
        cv2.circle(out,(x,y),7,palette[i],-1,cv2.LINE_AA)
        cv2.putText(out,f"{i+1} {POINT_NAMES[i]}",(max(0,x+9),max(24,y-7)),
                    cv2.FONT_HERSHEY_SIMPLEX,.55,(255,255,255),2,cv2.LINE_AA)
    cv2.polylines(out,[np.array(positions,np.int32)],True,(50,235,226),2,cv2.LINE_AA)
    return cv2.cvtColor(out,cv2.COLOR_BGR2RGB)


def show_calibration(job,snapshot):
    """Expandable expert tool; state is scoped to this analysis job only."""
    ref=Path(getattr(job,"reference_frame_file",""))
    objects=Path(getattr(job,"objects_file",""))
    if not ref.is_file() or not objects.is_file():
        st.info("A completed recorded-video analysis with a source camera frame is required.")
        return
    image=cv2.imread(str(ref))
    if image is None:
        st.error("Could not decode the source camera frame.")
        return
    h,w=image.shape[:2]
    key="surveyed_road_"+job.id
    st.write("Enter the four **surveyed corners of one flat road rectangle** in the original frame. "
             "These are percentages of frame width/height. The model will reject impossible or "
             "poorly fitted camera geometry and will not estimate physical distances without this survey.")
    with st.form("calibration_form_"+job.id):
        c1,c2=st.columns(2)
        width_m=c1.number_input("Measured patch width (metres)",min_value=1.,max_value=100.,
                                value=8.,step=.5,help="Physical road-plane width measured on site.")
        length_m=c2.number_input("Measured patch length (metres)",min_value=2.,max_value=1000.,
                                 value=25.,step=1.,help="Physical distance from near to far selected corners.")
        fov=st.number_input("Estimated horizontal camera FOV (degrees)",min_value=30.,
                            max_value=120.,value=70.,step=1.,
                            help="Use your camera specification if known. FOV errors alter inferred 3D camera pose.")
        table=pd.DataFrame({
            "Corner":POINT_NAMES,
            "Image X %":[20.,80.,60.,40.],
            "Image Y %":[85.,85.,40.,40.]
        })
        st.caption("The starting corner values are an EDITABLE EXAMPLE, not detected geometry. "
                   "Replace all four points with measured image locations.")
        edited=st.data_editor(table,hide_index=True,use_container_width=True,
                              disabled=["Corner"],num_rows="fixed",
                              column_config={
                                "Image X %":st.column_config.NumberColumn(min_value=0,max_value=100,step=.1,format="%.1f"),
                                "Image Y %":st.column_config.NumberColumn(min_value=0,max_value=100,step=.1,format="%.1f")
                              },key="calibration_editor_"+job.id)
        confirmed=st.checkbox("I checked these four physical road-plane corners and dimensions; "
                              "I understand a camera-only reconstruction cannot reveal unseen geometry.",
                              key="survey_confirmation_"+job.id)
        submitted=st.form_submit_button("Validate surveyed 3D calibration",type="primary")
    if submitted:
        if not confirmed:
            st.error("Confirm your actual measured geometry before enabling metric speed/3D claims.")
        else:
            try:
                points=tuple((float(row["Image X %"])/100,float(row["Image Y %"])/100)
                             for _,row in edited.iterrows())
                calibration=RoadCalibration(points,float(width_m),float(length_m))
                # This tests physical-pose consistency, not merely homography invertibility.
                pose=surveyed_road_scene(image,calibration,float(fov))
                if pose["reprojection_rmse_px"]>6:
                    raise ValueError("Perspective fit is too uncertain (camera reprojection > 6 px). "
                                     "Check corner order, FOV and whether the road is flat.")
                report=calibrated_tracks(objects,calibration,w,h)
                st.session_state[key]={
                    "calibration":{"points":points,"width_m":float(width_m),
                                   "length_m":float(length_m)},
                    "camera_fov_deg":float(fov),
                    "reprojection_error_px":pose["reprojection_rmse_px"],
                    "tracks_report":report,
                }
                st.success("Calibrated surveyed road plane. Detector has NOT been rerun; "
                           "all metric summaries were recomputed from the original tracked observations.")
            except (cv2.error,ValueError,TypeError,KeyError,OverflowError) as exc:
                st.error("Calibration rejected: "+str(exc))
    result=st.session_state.get(key)
    if not result:return
    cal_data=result["calibration"]
    cal=RoadCalibration(tuple(tuple(p) for p in cal_data["points"]),
                        cal_data["width_m"],cal_data["length_m"])
    st.image(annotated_frame(image,cal.points),
             caption="Your four surveyed corners on the ORIGINAL camera frame. "
                     "Do not treat unmeasured surrounding scenery as reconstructed geometry.",
             use_container_width=True)
    st.caption(f"Camera reprojection RMSE: {result['reprojection_error_px']} pixels; "
               f"survey patch: {cal.width_m:g} × {cal.length_m:g} metres. "
               "The FOV remains estimated unless independently known.")
    tracks=result["tracks_report"]
    a,b,c=st.columns(3)
    a.metric("Tracks with speed evidence",tracks["accepted_track_count"])
    b.metric("Median track speed (km/h)",
             str(tracks["median_track_speed_kmh"]) if tracks["median_track_speed_kmh"] is not None
             else "Not reliable")
    c.metric("Surveyed area (m²)",round(cal.width_m*cal.length_m))
    if tracks["tracks"]:
        st.dataframe(pd.DataFrame([{k:v for k,v in t.items() if k!="points"}
                                   for t in tracks["tracks"]]),hide_index=True,
                     use_container_width=True)
    else:
        st.warning("No tracks with enough reliable samples remained within the surveyed road patch. "
                   "No speed can be reported for this recording.")
    st.caption(tracks["basis"]["note"])
    st.download_button("Export surveyed measurements (JSON)",
                       json.dumps(tracks,indent=2),file_name="calibrated-road-tracks.json",
                       mime="application/json",key="survey_export_"+job.id)
    if st.button("Explore actual surveyed road in interactive 3D",type="primary",
                 use_container_width=True,key="survey_3d_"+job.id):
        st.session_state["survey_open_"+job.id]=True
    if st.session_state.get("survey_open_"+job.id):
        from calibrated_scene_view import show_surveyed_scene
        show_surveyed_scene(job,snapshot,cal,result["camera_fov_deg"])
