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
from premium_ui import STYLE, brand, legend, notice



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
        # Preserve the stronger small model on shared CPU but reduce
        # redundant full-resolution inference and CPU quota exhaustion.
        # Whole-video, time-spread sampling; never advertised as full FPS.
        image_size=1280 if gpu else 832,
        analysis_fps=10 if gpu else 3,
        detail_scan_every=8 if gpu else 14,
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
                st.image(snap["preview_jpeg"],caption="Current analyzed frame · colors mark proximity review indicators",use_container_width=True)
                legend()
                nearby = snap.get("proximity") or {}
                if nearby.get("pairs"):
                    nearest = nearby["pairs"][0]
                    if nearest.get("distance_m") is not None:
                        st.caption(f"Calibrated gap: {nearest['distance_m']:.1f} m · "
                                   f"Proximity tier: {nearest['level']} · Provisional, not a crash prediction.")
                    else:
                        st.caption("Yellow indicates image-space overlap for review. Actual distance and closing speed are not measurable from this uncalibrated footage.")
        if active and st.button("Stop analysis",key="simple_stop_"+job.id):
            job.stop()
        if state=="error" and not snap.get("analyzed_frames"):
            st.caption("No frames were analyzed. Try another video format or return later.")
    if not active and snap.get("analyzed_frames"):
        show_results(job,snap)
    return active


def video_tab():
    st.markdown(STYLE, unsafe_allow_html=True)
    brand()
    st.caption("VIDEO INTELLIGENCE / SIMPLE WORKSPACE")
    st.title("Understand any road video." if not st.session_state.get("simple_road_job") else "Your road, explained.")
    st.write("Upload a road recording and discover what is actually visible: traffic movement, moments to review, and evidence-led improvements. No technical setup required.")
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
            snapshot=current.snapshot()
            if snapshot["status"] in {"completed","stopped","ended","error"}:
                terminal_key="simple_road_terminal"
                if st.session_state.get(terminal_key)!=current.id:
                    st.session_state[terminal_key]=current.id
                    st.rerun(scope="app") # remove the periodic fragment schedule
            _status(current)
    _live()
    if not job:
        notice("Your recording stays the evidence source. Without measured camera geometry, the app shows image-only proximity review cues rather than invented distances, road speeds or collision probabilities.")
