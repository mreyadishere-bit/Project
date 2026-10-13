"""Single-page results experience: watch video, inspect evidence, understand next steps."""
from __future__ import annotations

import csv
from html import escape
import json

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from insight_engine import explain_video
from simulation_ui import simulation_panel
from reconstruction_ui import render_reconstruction


def _section(title: str, subtitle: str = ""):
    st.markdown(
        '<div class="sr-section-label"><h3>' + escape(title) +
        '</h3><p>' + escape(subtitle) + '</p></div>', unsafe_allow_html=True
    )


def activity_map(snap):
    """Overlay distribution of detected image contact points, not predicted hazards."""
    evidence = snap.get("evidence", {})
    data = np.asarray(evidence.get("footpoint_activity_grid", []), dtype=np.float32)
    base = snap.get("best_preview_jpeg") or snap.get("preview_jpeg")
    if not base or data.size == 0 or not data.max():
        return None
    image = cv2.imdecode(np.frombuffer(base, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    h,w = image.shape[:2]
    scaled = cv2.resize(data / max(1., float(data.max())), (w,h), interpolation=cv2.INTER_LINEAR)
    heat = cv2.applyColorMap((np.sqrt(scaled)*255).astype(np.uint8),cv2.COLORMAP_TURBO)
    opacity = (np.minimum(.67, scaled*.66))[...,None]
    composite = image.astype(np.float32)*(1-opacity) + heat.astype(np.float32)*opacity
    return cv2.cvtColor(np.clip(composite, 0,255).astype(np.uint8),cv2.COLOR_BGR2RGB)


def _numbers(snap):
    evidence = snap["evidence"]
    rates = evidence["percent_of_sampled_frames"]
    unique_tracks = sum(evidence["unique_track_ids_by_class"].values())
    sections = [
        ("Frames analyzed", f"{snap['analyzed_frames']:,}", "Sampled"),
        ("Track IDs recorded", f"{unique_tracks:,}", "May change after occlusion"),
        ("Visible vehicles / frame", f"{evidence['averages_per_frame']['vehicles']:.1f}", "Average sampled frame"),
        ("Pedestrian frames", f"{rates['pedestrians']:.1f}%", "With ≥1 detected person"),
        ("Close-image frames", f"{rates['close_in_image']:.1f}%", "Not real distance"),
        ("Dark-image frames", f"{rates['dark_image']:.1f}%", "Camera exposure matters"),
    ]
    html = '<div class="sr-metric-grid sr-metric-six">'
    for name,value,unit in sections:
        html += (f'<div class="sr-metric"><span class="sr-metric-kicker">{escape(name)}</span>'
                 f'<strong>{escape(value)}</strong>'
                 f'<div style="color:#91a0ae;font-size:11px;margin-top:10px">{escape(unit)}</div></div>')
    st.markdown(html+'</div>',unsafe_allow_html=True)


def _timeline(job,snap):
    if not job.events_file.exists():
        st.caption("No diagnostic event log was written.")
        return
    rows = []
    with job.events_file.open(encoding="utf-8-sig",newline="") as src:
        for row in csv.DictReader(src):
            rows.append(row)
            if len(rows) >= 250:
                break
    if not rows:
        st.success("No experimental diagnostic events recorded. This does not prove the road is safe.")
    else:
        chart = pd.DataFrame(rows)
        chart["video_second"] = pd.to_numeric(chart["video_second"],errors="coerce")
        st.dataframe(
            chart[["video_second","title","description"]].rename(columns={
                "video_second":"Video second","title":"Observation","description":"What was measured"
            }), hide_index=True,use_container_width=True,height=min(320, 70+len(rows)*35)
        )
        if len(rows) == 250:
            st.caption("Showing first 250 events. Download the full CSV for the complete event timeline.")


def results_page(job, snap, hosted: bool):
    if not snap or not snap.get("analyzed_frames"):
        return
    evidence = snap.get("evidence") or {}
    story = explain_video(evidence,snap["label"])
    status = snap.get("status")
    if status in {"stopped","error"}:
        st.warning("Partial analysis: this job did not process the entire video. The report covers only analyzed frames.")
    elif status not in {"completed","ended"}:
        st.caption("Preliminary results are updating; wait until the video finishes for the final report.")

    st.markdown('<div class="sr-results-header"><div class="sr-eyebrow">COMPLETE VIDEO INTELLIGENCE</div>'
                '<h2>Your analysis, explained.</h2><p>كل النتائج والتوصيات والفيديو النهائي والمحاكاة في مكان واحد.</p>'
                '</div>',unsafe_allow_html=True)
    _section("01 · Executive overview","Actual sampled evidence, not a fabricated crash forecast")
    left,right=st.columns([2.2,1],gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("#### What the video showed")
            st.write(story["description"])
            st.caption(
                f"Full-video sample: {evidence.get('analyzed_frames',0):,} frames. "
                "Detector/tracker can miss objects or change IDs. Road-surface defects "
                "and verified near misses are NOT detected by the current model."
            )
            rates=evidence.get("percent_of_sampled_frames",{})
            st.info(
                f"**ملخص بسيط:** تم تحليل {evidence.get('analyzed_frames',0):,} إطار. "
                f"المركبات ظاهرة في {rates.get('vehicles',0)}% من الإطارات، "
                f"والمشاة في {rates.get('pedestrians',0)}%، "
                f"وفي {rates.get('close_in_image',0)}% ظهرت أجسام قريبة في الصورة. "
                "ده مش قياس للمسافة الحقيقية ولا احتمال وقوع حادث."
            )
    with right:
        with st.container(border=True):
            st.markdown("#### Human review priority")
            priority=story["priority"]
            score=priority["score"]
            if score is None:
                st.markdown("### Not enough evidence")
            else:
                st.markdown(f"### {score} / 100")
            st.markdown("**"+priority["level"]+"**")
            st.caption(priority["explanation"])
            st.caption("Higher means more sampled frames matched exploratory flags. Not a road safety grade.")

    _numbers(snap)
    _section("Vehicle flow through a counting line","Passed vehicles are measured separately from objects visible in any one frame")
    crossing=snap.get("crossings") or {}
    c1,c2,c3=st.columns(3)
    c1.metric("Vehicles crossing the line",crossing.get("total_passed",0),
              help="Unique tracked vehicles whose detected footpoints cross the chosen line exactly once; tracker dropouts can affect counts.")
    c2.metric("Track IDs seen",sum(evidence.get("unique_track_ids_by_class",{}).values()),
              help="Not equivalent to actual unique cars passing the camera.")
    c3.metric("Peak simultaneously visible",snap.get("max_vehicles",0),
              help="Maximum vehicles in any single sampled frame; not total traffic.")
    st.caption(f"Counting line at {100*crossing.get('line_y_fraction',.5):.0f}% of frame height. If a vehicle never crosses the line, it isn't counted. If a track breaks, some cars may be missed or double-counted.")
    if crossing.get("passed_by_class"):
        st.bar_chart(pd.DataFrame(
            [{"Class":name,"Passed":count} for name,count in crossing["passed_by_class"].items()]
        ).set_index("Class"),height=180)
    if snap.get("calibration"):
        st.caption("Road-plane homography calibration was supplied; per-track estimated world positions, headings and km/h are included in the object CSV. These are NOT validated speed-enforcement measurements.")
    else:
        st.caption("Road-plane calibration not supplied; real-world speed/angle outputs are not claimed.")

    _section("02 · Final analyzed video","Play the result here, not in a separate file")
    if snap.get("video_ready") and job.video_file.exists():
        with st.container(border=True):
            st.video(str(job.video_file),format="video/mp4")
            st.caption(
                "Browser-playable H.264 · sampled frames span the processed source timeline "
                f"(target {snap.get('settings_fps', '?')} analyzed frames/video second). "
                "Original audio is not included. This is a time-sampled annotation, "
                "not every original camera frame."
            )
            if job.video_file.stat().st_size <= 170*1024*1024:
                st.download_button("Download annotated analysis video ↓",
                    job.video_file.read_bytes(), file_name="smart-road-analyzed.mp4",
                    mime="video/mp4",key="download_final_annotated")
            else:
                st.caption("Large video export is saved on the server. Process locally for very large file downloads.")
    else:
        if status == "finalizing video":
            st.info("Encoding the final H.264 video for browser playback...")
        elif snap.get("video_export_error"):
            st.warning("Video analysis is complete, but the browser video could not be encoded: " + snap["video_export_error"])
        elif not job.settings.save_video:
            st.info("Annotated video export was disabled for this run. Enable **Create final playable video** before the next analysis to generate a playable result.")
        else:
            st.warning("No playable video file is available for this run.")
        if snap.get("best_preview_jpeg"):
            st.image(snap["best_preview_jpeg"],caption="Representative analyzed frame (not a video)",use_container_width=True)

    _section("03 · Patterns in the full video","See how traffic changed over time")
    viewleft,viewright=st.columns([1.35,1],gap="large")
    with viewleft:
        if job.summary_file.exists():
            # Read a bounded sample for interactive chart; all rows remain in downloadable CSV.
            samples=[]
            with job.summary_file.open(encoding="utf-8-sig",newline="") as src:
                for i,row in enumerate(csv.DictReader(src)):
                    if i % max(1, snap["analyzed_frames"]//600) == 0:
                        samples.append(row)
                    if len(samples)>=650:
                        break
            if samples:
                df=pd.DataFrame(samples)
                for k in ("video_second","vehicles","people"):
                    df[k]=pd.to_numeric(df[k],errors="coerce").fillna(0)
                st.line_chart(df.set_index("video_second")[["vehicles","people"]],height=292)
        st.caption("Vehicles and pedestrians visible in each sampled frame; NOT distinct passing traffic counts.")
    with viewright:
        heat=activity_map(snap)
        if heat is not None:
            st.image(heat,use_container_width=True)
            st.caption("Activity density: where detection bottom-centres appeared most often (hot ≠ dangerous).")
        else:
            st.caption("Not enough detected object positions for an activity map.")

    _section("04 · Noteworthy observations","When the system flagged conditions for review")
    _timeline(job,snap)

    _section("05 · Practical recommendations","What to investigate and how to confirm it")
    for i, rec in enumerate(story["recommendations"],1):
        with st.container(border=True):
            cols=st.columns([.16,2.8])
            cols[0].markdown(f"### {i:02d}")
            with cols[1]:
                st.markdown(f"**{rec['title']}**")
                st.caption(f"Review priority: {rec['priority'].upper()}")
                st.write("**Why:** "+rec["reason"])
                st.write("**Suggested step:** "+rec["action"])
                st.caption("Verification before real construction: "+rec["verify"])
    st.caption("These recommendations are rule-based explanations grounded in detector observations. They are not licensed engineering designs or measured benefits.")

    _section("06 · Video-matched 3D scene replay","Track positions and original timestamps with editable 3D scene interventions")
    render_reconstruction(job,snap)
    _section("07 · Additional traffic simulation","Compare hypothetical traffic scenarios in a separate simplified 2.5D model")
    simulation_panel()

    _section("08 · Download your full analysis","Transparent evidence and documented assumptions")
    report={
        "project":"Smart Road AI research v4",
        "source":snap["label"],
        "job_id":job.id,
        "analysis_status":snap["status"],
        "analyzed_frames":snap["analyzed_frames"],
        "evidence":evidence,
        "crossings":snap.get("crossings"),
        "calibration":snap.get("calibration"),
        "plain_language_summary":story,
        "limitations":[
            "Image proximity is not a physical near miss.",
            "Speed in px/s is not real-world velocity; optional scale values are approximate.",
            "Tracking IDs may change after occlusion.",
            "No pothole, flood or traffic signal state specialist model is installed.",
            "Toy 2.5D simulation uses user assumptions and is NOT fitted to camera geometry."
        ]
    }
    st.download_button("Download complete evidence report (JSON) ↓",
         json.dumps(report,ensure_ascii=False,indent=2),file_name="smart-road-full-analysis.json",
         mime="application/json",key="sr_report_v4")
    with st.expander("Download detailed CSV evidence"):
        for path,name in [
            (job.summary_file,"Per-frame traffic observations"),
            (job.objects_file,"Full object observations and tracks"),
            (job.events_file,"Complete diagnostic event timeline"),
        ]:
            if path.exists():
                mb=path.stat().st_size/(1024*1024)
                if mb <= 95:
                    st.download_button(f"{name} · {mb:.1f} MB ↓",path.read_bytes(),
                                       file_name=path.name,mime="text/csv",key="sr_evidence_"+path.name)
                else:
                    st.caption(f"{name}: {mb:.1f} MB. Process locally for oversized exports.")
    st.caption("Not for real-time driver warnings, automated speed enforcement, or unreviewed infrastructure decisions.")
