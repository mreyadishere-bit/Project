"""Lightweight source-frame evidence visualization, not a fictitious twin.

Actual original frame on both sides. Only a discrete location outline and
traceable, conditional review advice are added. No synthetic vehicles,
arbitrary zebras, yellow-circle spam, or unsupported crash-reduction claim.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
import streamlit as st
from video_comparison import source_video_path


@st.cache_data(show_spinner=False,max_entries=18,ttl=3600)
def _source_frame(path:str, file_size:int, mtime_ns:int, timestamp:float):
    """Decode one real video frame at a requested event second on demand."""
    capture=cv2.VideoCapture(path)
    if not capture.isOpened():
        return None
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC,max(0,timestamp)*1000)
        ok,frame=capture.read()
        if not ok:
            return None
        h,w=frame.shape[:2]
        if w>1000:
            frame=cv2.resize(frame,(1000,round(h*1000/w)),interpolation=cv2.INTER_AREA)
        success,jpeg=cv2.imencode(".jpg",frame,[cv2.IMWRITE_JPEG_QUALITY,83])
        return jpeg.tobytes() if success else None
    finally:
        capture.release()


def highlight_photo(image_bytes,loc,tag):
    """Four unobtrusive cyan corner brackets instead of warning circles."""
    im=cv2.imdecode(np.frombuffer(image_bytes,dtype=np.uint8),cv2.IMREAD_COLOR)
    if im is None:
        raise ValueError("Could not decode the real evidence frame.")
    h,w=im.shape[:2]
    x=int(float(loc[0])*w);y=int(float(loc[1])*h)
    if not(0<=x<w and 0<=y<h):
        raise ValueError("Image point outside original video.")
    reach=max(24,int(min(w,h)*.07))
    left,right=max(0,x-reach),min(w-1,x+reach)
    top,bottom=max(0,y-reach),min(h-1,y+reach)
    stroke=max(2,round(w/450))
    segment=max(10,reach//2)
    cyan=(226,160,29)
    for a,b,dx,dy in (
        (left,top,1,1),(right,top,-1,1),
        (left,bottom,1,-1),(right,bottom,-1,-1),
    ):
        cv2.line(im,(a,b),(a+dx*segment,b),cyan,stroke,cv2.LINE_AA)
        cv2.line(im,(a,b),(a,b+dy*segment),cyan,stroke,cv2.LINE_AA)
    panel=im.copy()
    overlay_h=min(h,42)
    cv2.rectangle(panel,(0,0),(w,overlay_h),(18,31,48),-1)
    cv2.addWeighted(panel,.75,im,.25,0,im)
    cv2.putText(im,tag[:76],(12,min(h-8,29)),cv2.FONT_HERSHEY_SIMPLEX,
                max(.40,min(.62,w/1500)),(255,255,255),2,cv2.LINE_AA)
    return cv2.cvtColor(im,cv2.COLOR_BGR2RGB)


def display_source_review(job,moments):
    if not moments:
        st.info("No video-localized issue passed the conservative image-evidence checks. "
                "This does NOT mean the road is safe. Annotated results and field inspection are still needed.")
        return
    real=source_video_path(job)
    if real is None:
        st.warning("The original recording is unavailable; not substituting a generic road model for it.")
        return
    choices=list(range(len(moments)))
    selected=st.selectbox(
        "Find a moment worth reviewing",
        choices,
        format_func=lambda i:f"{moments[i]['video_second']:.1f}s · {moments[i]['title']}",
        key="source_review_event_"+job.id
    )
    event=moments[selected]
    stat=real.stat()
    with st.spinner("Opening this location in your original video…"):
        frame=_source_frame(str(real),stat.st_size,stat.st_mtime_ns,
                            round(float(event["video_second"]),1))
    if frame is None:
        st.warning("The recorded timestamp could not be decoded. Use the full video player above.")
        return
    col1,col2=st.columns(2,gap="small")
    with col1:
        st.markdown("**01 · Original road, unchanged**")
        st.image(frame,use_container_width=True)
        st.caption(f"Camera frame near {event['video_second']:.1f}s, no generated scenery.")
    with col2:
        st.markdown("**02 · Evidence location on the same road**")
        image=highlight_photo(frame,event["image_location"],"REVIEW THIS RECORDED LOCATION")
        st.image(image,use_container_width=True)
        st.caption("Cyan brackets locate the tracked observation in image coordinates. "
                   "They do not represent danger radius or measured physical road distance.")
    with st.container(border=True):
        st.markdown("**Why this exact scene deserves attention**")
        st.write(event["evidence"])
        st.markdown("**What an appropriate improvement could involve**")
        st.write(event["review_action"])
        st.caption("Provisional, requires field verification. A road sign, crossing or traffic "
                   "signal is NOT placed automatically without verified road geometry, "
                   "traffic directions, existing facilities and crossing rules.")
        st.caption("This is a source-video-grounded review, NOT a synthetic 3D improvement "
                   "or a measured reduction in collisions.")
        if st.button(f"Play the original video near {event['video_second']:.1f}s",
                     key="open_original_scene_"+job.id,use_container_width=True):
            st.session_state["source_playback_"+job.id]=int(max(0,event["video_second"]-2))
        if "source_playback_"+job.id in st.session_state:
            st.video(str(real),start_time=st.session_state["source_playback_"+job.id])
