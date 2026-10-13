"""Smart Road — upload once, automatic best practical analysis, useful results.

No user-facing AI, tracking, camera geometry or speed settings.
"""
from __future__ import annotations
from pathlib import Path
import importlib.util
import os
import shutil
import uuid

import streamlit as st
from video_engine import VideoJob, VideoSettings, OUTPUTS
from simple_results import show_results

STYLE="""
<style>
.block-container{max-width:1150px;padding-top:2rem;padding-bottom:4rem}
html,body,[data-testid="stAppViewContainer"]{background:#f7f9fc}
h1,h2,h3{letter-spacing:-.048em}
h1{font-size:clamp(2rem,5vw,3.4rem)!important}
[data-testid="stVerticalBlockBorderWrapper"] > div{border-color:#e3e9f2!important;border-radius:20px!important}
div[data-testid="stMetric"]{background:white;border:1px solid #e2e8f1;border-radius:15px;padding:15px}
.stButton>button[kind="primary"]{border-radius:14px;background:#2468c6;border:0;min-height:48px}
[data-testid="stFileUploader"]{border-radius:18px}
[data-testid="stAlert"]{border-radius:14px}
@media(max-width:700px){.block-container{padding:1.2rem .9rem 3rem}h1{font-size:2.2rem!important}}
</style>
"""

def _store_video(upload):
    ext=Path(upload.name).suffix.lower()
    if ext not in {".mp4",".mov",".mkv",".avi",".m4v"}:
        raise ValueError("Choose an MP4, MOV, MKV, AVI, or M4V video.")
    root=OUTPUTS/"uploads"
    root.mkdir(parents=True,exist_ok=True)
    dest=root/(uuid.uuid4().hex+ext)
    try:
        upload.seek(0)
        with dest.open("wb") as f:
            shutil.copyfileobj(upload,f,length=1024*1024)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return str(dest)


def _automatic_settings():
    # A faster model run across the *entire* clip beats sampling almost no
    # frames with a huge model on a free 2-core instance.
    try:
        import torch
        gpu=bool(torch.cuda.is_available())
    except ImportError:
        gpu=False
    # All reasonable quality/detection options set automatically by hardware.
    return VideoSettings(
        model_name="yolo26m.pt" if gpu else "yolo26s.pt",
        image_size=1280 if gpu else 960,
        analysis_fps=10 if gpu else 5,
        confidence=.12,
        tracker="traffic_botsort.yaml",
        save_video=True,
        count_line_fraction=.52,
        use_openvino=False,
    )


def _status(job):
    snap=job.snapshot()
    state=snap["status"]
    active=state in {"starting","loading model","connecting stream","running","finalizing video"}
    with st.container(border=True):
        if state=="loading model":
            st.info("Loading the AI vision model for your video…")
        elif state=="finalizing video":
            st.info("Analysis complete. Preparing the playable final video…")
        elif state=="error":
            st.error("This analysis could not finish: "+snap.get("error","Unknown error"))
        elif state in {"completed","ended","stopped"}:
            if state=="stopped":st.warning("This analysis was stopped; results may be incomplete.")
            else:st.success("Analysis complete.")
        else:
            st.markdown("**Analyzing your road…**")
        if snap.get("analyzed_frames"):
            c1,c2,c3=st.columns(3)
            c1.metric("Frames inspected",snap["analyzed_frames"])
            c2.metric("Vehicles passed",snap.get("crossings",{}).get("total_passed",0))
            c3.metric("AI frames/second",f"{snap.get('processing_fps',0):.1f}")
            if snap.get("duration_seconds",0):
                pct=min(1,max(0,snap["video_second"]/snap["duration_seconds"]))
                st.progress(pct,text=f"{pct:.0%} of video timeline inspected")
            if snap.get("preview_jpeg") and active:
                st.image(snap["preview_jpeg"],caption="Current analyzed frame",use_container_width=True)
        if active and st.button("Stop analysis",key="simple_stop_"+job.id):
            job.stop()
        if state=="error" and not snap.get("analyzed_frames"):
            st.caption("No frames were analyzed. Try another video format or return later.")
    if not active and snap.get("analyzed_frames"):
        show_results(job,snap)
    return active


def video_tab():
    st.markdown(STYLE,unsafe_allow_html=True)
    st.caption("SMART ROAD  /  AI VISION LAB")
    st.title("Understand any road video.")
    st.write("Upload traffic footage. Smart Road automatically analyzes movement, counts, and possible improvements—then shows the video and a scene-based simulation.")
    job=st.session_state.get("simple_road_job")
    snap=job.snapshot() if job else None
    busy=bool(snap and snap["status"] in {
        "starting","loading model","connecting stream","running","finalizing video"
    })
    if not busy:
        with st.container(border=True):
            video=st.file_uploader(
                "Choose your road video",
                type=["mp4","mov","mkv","avi","m4v"],
                key="simple_road_upload",
                help="Use a fixed road-camera view with clear traffic. Video contents are processed on this app's server."
            )
            if video:
                st.caption(f"{video.name} · {video.size/1024/1024:.1f} MB")
            if st.button("Analyze road",type="primary",use_container_width=True,
                         disabled=video is None,key="simple_road_start"):
                try:
                    source=_store_video(video)
                    settings=_automatic_settings()
                    st.session_state["simple_road_job"]=VideoJob(
                        source,settings,label=video.name,source_kind="file")
                    st.rerun()
                except (OSError,ValueError,RuntimeError) as exc:
                    st.error(str(exc))
    else:
        st.caption("You don't need to adjust any settings. The analysis automatically uses the appropriate preset for the server.")

    @st.fragment(run_every=1.4 if busy else None)
    def _live():
        current=st.session_state.get("simple_road_job")
        if current:
            _status(current)
    _live()
    if not job:
        st.caption("No calibration is assumed: physical speeds and exact road dimensions will not be invented from one camera.")
