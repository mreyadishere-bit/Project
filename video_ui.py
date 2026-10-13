"""Smart Road AI — premium video analysis workspace.

Native controls for accessibility, evidence-first analytics, bounded live updates.
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
import os
import shutil
import uuid

import pandas as pd
import streamlit as st

from ui_theme import apply_theme
from video_engine import VideoJob, VideoSettings, OUTPUTS
from live_sources import canonical_youtube_live_url
from public_cameras import get_camera, camera_choices
from results_ui import results_page

STATUS = {
    "starting": ("Starting", "blue"),
    "connecting stream": ("Checking video source", "blue"),
    "loading model": ("Loading AI model", "blue"),
    "running": ("Analyzing", "green"),
    "completed": ("Completed", "green"),
    "finalizing video": ("Encoding final video", "blue"),
    "stopped": ("Stopped", "amber"),
    "ended": ("Broadcast ended", "amber"),
    "error": ("Needs attention", "red"),
}
PRESETS = {
    "Quick scan": ("yolo26n.pt", 2, 512),
    "Balanced": ("yolo26n.pt", 5, 640),
    "Deep analysis": ("yolo26s.pt", 10, 640),
    "Custom": (None, None, None),
}
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".m4v"}


def save_uploaded_video(file):
    """Copy the uploaded bytes to a unique local location, without buffering all in RAM."""
    folder = OUTPUTS / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(file.name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported video format; use MP4, AVI, MOV, MKV or M4V.")
    dest = folder / (uuid.uuid4().hex + ext)
    try:
        file.seek(0)
        with dest.open("wb") as output:
            shutil.copyfileobj(file, output, length=8 * 1024 * 1024)
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    return dest


def section_header(title, subtitle=""):
    st.markdown(
        '<div class="sr-section-label"><h3>' + escape(title) +
        '</h3><p>' + escape(subtitle) + '</p></div>',
        unsafe_allow_html=True
    )


def metric_cards(items):
    blocks = []
    for label, value, unit, style in items:
        blocks.append(
            '<div class="sr-metric ' + escape(style) + '">'
            '<span class="sr-metric-kicker">' + escape(str(label)) + '</span>'
            '<strong>' + escape(str(value)) + '</strong>'
            '<span class="sr-metric-unit">' + escape(str(unit)) + '</span></div>'
        )
    st.markdown('<div class="sr-metric-grid">' + ''.join(blocks) + '</div>', unsafe_allow_html=True)


def brand(hosted, snap):
    status = (snap or {}).get("status", "")
    label, tone = STATUS.get(status, ("Research preview", "blue"))
    st.markdown(
        '<div class="sr-topbar"><div class="sr-brand">'
        '<div class="sr-symbol"><svg width="24" height="24" viewBox="0 0 24 24" fill="none">'
        '<path d="M7.5 19 10.4 5m6.1 14L13.6 5" stroke="white" stroke-width="2.2" stroke-linecap="round"/>'
        '<path d="M12 7.3v2.2m0 3.5v3.8" stroke="#8bc7ff" stroke-width="2" stroke-linecap="round"/>'
        '</svg></div><div class="sr-wordmark">Smart Road <span style="color:#3386eb">AI</span>'
        '<small>ROAD INTELLIGENCE LAB</small></div></div>'
        '<div class="sr-topright">'
        '<span class="sr-topchip"><span class="sr-dot"></span>' + escape(label) + '</span>'
        '<span class="sr-topchip">' + ("CLOUD / CPU" if hosted else "LOCAL WORKSPACE") + '</span>'
        '<span class="sr-topchip">RESEARCH BUILD · V3</span>'
        '</div></div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="sr-hero"><div>'
        '<div class="sr-eyebrow">Vision intelligence / Scene diagnostics</div>'
        '<h1>Understand the road.<br>Before risks escalate.</h1>'
        '<p>Track traffic, inspect what the camera can actually observe, and turn long footage into clear, reviewable evidence. '
        'مصمم لتحليل المشاهد المرورية بصورة منظمة وشفافة، مع عرض حدود دقة كل قياس.</p>'
        '</div><div class="sr-hero-mini">'
        '<div class="sr-mini-stat"><span>PRIMARY ANALYSIS</span><b>Detection + tracking</b></div>'
        '<div class="sr-mini-stat"><span>PROCESSING</span><b>Frame by frame</b></div>'
        '</div></div>', unsafe_allow_html=True
    )


def feature_tiles():
    st.markdown(
        '<div class="sr-tech-grid">'
        '<div class="sr-tech"><span class="sr-tag green">AVAILABLE</span><b>Objects & trajectories</b>'
        '<p>Cars, trucks, buses, people and tracked IDs with visible motion patterns.</p></div>'
        '<div class="sr-tech"><span class="sr-tag green">EXPERIMENTAL</span><b>Scene diagnostics</b>'
        '<p>Brightness, apparent crowding, image proximity, and pixel motion.</p></div>'
        '<div class="sr-tech"><span class="sr-tag amber">REQUIRES SPECIALIZED AI</span><b>Road defects & near misses</b>'
        '<p>True pothole models, calibrated distances and collision prediction are not enabled yet.</p></div>'
        '</div>', unsafe_allow_html=True
    )


def source_and_settings(hosted: bool, running: bool):
    """Draw inputs and return validated form selections without starting jobs."""
    section_header("New analysis", "01 / Choose a source and processing profile")
    with st.container(border=True):
        options = ["Upload video", "Free Live Traffic Cameras", "YouTube Live (beta)"]
        if not hosted:
            options += ["Local file", "PC camera"]
        source_mode = st.radio("Video source", options, horizontal=True, disabled=running, key="sr_source")
        if hosted:
            st.caption("Cloud CPU · public live broadcasts may be inaccessible due to provider restrictions · no guaranteed low latency.")
        uploaded = None
        source = None
        label = ""
        if source_mode == "Free Live Traffic Cameras":
            choices = camera_choices()
            source = st.selectbox(
                "Public agency traffic camera", list(choices),
                format_func=lambda key: choices[key],
                key="sr_official_camera", disabled=running
            )
            camera = get_camera(source)
            label = camera["label"]
            st.caption(f"Source: {camera['operator']} · {camera['region']}")
            st.caption("Real agency HLS video, when operational · Free to view · No YouTube extractor. Availability can change.")
            st.link_button("Official camera directory & terms ↗", camera["info_url"])
            if st.button("Check first video frame", disabled=running, key="sr_check_public_camera"):
                with st.spinner("Checking for a real frame (up to 18 seconds)..."):
                    try:
                        from camera_check import check_first_frame
                        frame = check_first_frame(camera["stream_url"])
                        st.session_state["sr_camera_verified"] = (source, frame)
                    except Exception as exc:
                        st.session_state.pop("sr_camera_verified", None)
                        st.warning(f"Camera is currently unreachable from this server: {exc}")
            verified = st.session_state.get("sr_camera_verified")
            if verified and verified[0] == source:
                st.success("Verified: an actual video frame arrived from this camera.")
                st.image(verified[1], use_container_width=True)
                st.caption("One camera frame. AI starts only after clicking Start analyzing.")
        elif source_mode == "Upload video":
            uploaded = st.file_uploader(
                "Drop your footage here", type=["mp4", "avi", "mov", "mkv", "m4v"],
                disabled=running, key="sr_video_upload",
                help="Supported: MP4, MOV, MKV, AVI, M4V. Cloud storage and computation are limited."
            )
            if uploaded:
                label = uploaded.name
                st.caption(f"Selected: {uploaded.name} · {uploaded.size / 1024**2:.1f} MB")
        elif source_mode == "YouTube Live (beta)":
            source = st.text_input(
                "Public YouTube LIVE URL", placeholder="https://www.youtube.com/live/VIDEO_ID",
                key="sr_youtube_url", disabled=running,
                help="Use an active public YouTube live video you are authorized to analyze, not a channel or playlist URL."
            )
            label = "YouTube public live broadcast"
            st.caption("Experimental live analysis, not synchronized with the YouTube player. Only a permitted, accessible broadcast can be processed. Stream availability and delay are outside our control.")
            if source:
                try:
                    st.link_button("Watch original video on YouTube ↗",
                                   canonical_youtube_live_url(source))
                except ValueError:
                    pass
        elif source_mode == "Local file":
            value = st.text_input(
                "Absolute file path on this computer", key="sr_local_path",
                placeholder=r"C:\Users\You\Videos\road.mp4", disabled=running
            )
            source = value.strip().strip('"')
            label = Path(source).name if source else ""
            st.caption("Local files are streamed from disk, with no fixed one-minute limit.")
        else:
            source = int(st.selectbox("Connected camera", [0, 1, 2], disabled=running))
            label = f"PC camera {source}"
            st.caption("Captures the camera attached to the computer hosting this Python process.")

        st.markdown("**Analysis profile**")
        preset = st.radio("Choose performance", list(PRESETS), horizontal=True,
                          label_visibility="collapsed", key="sr_preset", disabled=running)
        model, fps, image_size = PRESETS[preset]
        with st.expander("Fine-tune detection & export", expanded=(preset == "Custom" and not running)):
            c1, c2 = st.columns(2)
            with c1:
                if preset == "Custom":
                    model = st.selectbox("Detection model", ["yolo26n.pt", "yolo26s.pt", "yolo26m.pt"],
                                         disabled=running)
                    fps = st.select_slider("Frames analyzed / video second", [1, 2, 5, 10, 15, 30],
                                           value=5, disabled=running)
                    image_size = st.selectbox("Inference image size", [416, 512, 640, 960],
                                              index=2, disabled=running)
                confidence = st.slider("Minimum confidence", .1, .9, .35, .05, disabled=running)
            with c2:
                all_classes = st.checkbox("Detect all supported YOLO classes", value=False, disabled=running)
                save_video = st.checkbox("Create final playable video (H.264)", value=True, disabled=running or source_mode in {"PC camera", "YouTube Live (beta)", "Free Live Traffic Cameras"},key="sr_export_video")
                if save_video:
                    st.caption("Creates the full-timeline, time-sampled annotated MP4 after analysis. H.264 export takes additional time and disk space; original audio is not kept.")
        with st.expander("Speed calibration (optional, research only)"):
            calibrate = st.checkbox("I have a measured metres-per-pixel scale for this camera",
                                    disabled=running, key="sr_calibrate")
            meters_per_pixel = None
            if calibrate:
                meters_per_pixel = st.number_input(
                    "Approximate metres per image pixel", min_value=0.0001, max_value=100.0,
                    value=0.025, step=0.005, format="%.4f", disabled=running
                )
                st.warning("A constant scale cannot correct perspective. The km/h values are rough estimates near the calibration region, not radar speeds or legal evidence.")
            else:
                st.caption("Without calibration, motion is shown in pixels/second. The system will NOT invent real-world vehicle speeds.")

        start = st.button("Start analyzing  →", type="primary", disabled=running,
                          use_container_width=True, key="sr_start")
        if start:
            try:
                if source_mode == "Upload video":
                    if uploaded is None:
                        raise ValueError("Upload a video first.")
                    with st.spinner("Preparing video..."):
                        actual = str(save_uploaded_video(uploaded))
                elif source_mode == "Free Live Traffic Cameras":
                    actual = str(source)
                    get_camera(actual)
                elif source_mode == "YouTube Live (beta)":
                    if not source:
                        raise ValueError("Paste an active public YouTube LIVE video URL.")
                    actual = canonical_youtube_live_url(source)
                elif source_mode == "Local file":
                    if not source or not Path(source).is_file():
                        raise ValueError("Choose a valid local video path.")
                    if Path(source).suffix.lower() not in ALLOWED_EXTENSIONS:
                        raise ValueError("Unsupported video file extension.")
                    actual = str(Path(source).resolve())
                else:
                    actual = source
                st.session_state["video_job"] = VideoJob(
                    actual, VideoSettings(
                        model_name=model, confidence=confidence, image_size=image_size,
                        analysis_fps=fps, all_classes=all_classes,
                        save_video=bool(save_video and source_mode not in {"PC camera", "YouTube Live (beta)", "Free Live Traffic Cameras"}),
                        meters_per_pixel=meters_per_pixel
                    ), label=label, source_kind=("youtube" if source_mode == "YouTube Live (beta)" else "public_live" if source_mode == "Free Live Traffic Cameras" else "file")
                )
                st.rerun()
            except Exception as exc:
                st.error(f"Could not start: {exc}")


def video_stage(snap, job):
    section_header("Live visual analysis", "02 / Current sampled frame & processing status")
    left, right = st.columns([1.8, 1], gap="medium")
    with left:
        with st.container(border=True):
            if (snap and snap.get("source_kind") == "public_live"
                    and snap.get("status") == "error" and not snap.get("preview_jpeg")):
                st.warning("This official camera could not supply any frames. No AI analysis took place.")
                details = get_camera(job.source)
                st.link_button("See the official camera directory ↗", details["info_url"])
            elif (snap and snap.get("source_kind") == "youtube"
                    and snap.get("status") == "error" and not snap.get("preview_jpeg")):
                st.warning("YouTube player preview only — 0 frames reached the AI. This is NOT an analyzed video.")
                st.video(job.source)
                st.caption("Playback can be available in your browser even when YouTube blocks server-side frame extraction.")
            elif snap and snap.get("source_kind") in {"youtube", "public_live"} and snap.get("status") == "running" and not snap.get("preview_jpeg"):
                st.info("Connecting to live video frames through FFmpeg. The AI has not received an image yet. If decoding cannot start, the job will report an error rather than displaying imaginary detections.")
                st.markdown(
                    '<div class="sr-empty" style="min-height:260px"><div class="sr-empty-icon">⌁</div>'
                    '<strong>Waiting for the first decoded frame</strong>'
                    '<p>YouTube playback and server-side AI processing are independent.</p></div>',
                    unsafe_allow_html=True,
                )
            elif snap and snap.get("preview_jpeg"):
                show_best = bool(snap["status"] in {"completed", "stopped", "ended"} and
                                 not snap.get("detected_now", {}).get("all_objects") and snap.get("best_preview_jpeg"))
                st.image(snap["best_preview_jpeg"] if show_best else snap["preview_jpeg"], use_container_width=True)
                if show_best:
                    st.caption(f"Representative detected frame at {snap['best_preview_at']:.1f}s · The very last frame had no detected objects.")
                else:
                    st.caption(f"Latest analyzed frame · {snap['video_second']:.1f}s · Overlays are model estimates.")
                if snap.get("source_kind") in {"youtube", "public_live"}:
                    st.caption("LIVE SOURCE · Results are based on sampled decoded frames and can lag behind the broadcast.")
            else:
                st.markdown(
                    '<div class="sr-empty"><div class="sr-empty-icon">⌁</div>'
                    '<strong>Your scene starts here</strong>'
                    '<p>Upload footage and start an analysis to see tracked objects, live counts and observed scene conditions.</p>'
                    '</div>', unsafe_allow_html=True
                )
    with right:
        with st.container(border=True):
            if not snap:
                st.markdown("**Session readiness**")
                st.markdown('<span class="sr-tag blue">WAITING FOR A VIDEO</span>', unsafe_allow_html=True)
                st.caption("Nothing has been processed yet. Start with a 1–3 minute clip to verify the pipeline.")
            else:
                label, tone = STATUS.get(snap["status"], ("Research", "blue"))
                st.markdown(f"**Processing status**")
                st.markdown('<span class="sr-tag ' + tone + '">' + escape(label.upper()) + '</span>', unsafe_allow_html=True)
                st.caption(f"Source: {snap['label']}")
                st.caption(f"Compute: {snap['device']}")
                st.caption(f"Analyzed frames: {snap['analyzed_frames']:,}")
                st.caption(f"Processing throughput: {snap['processing_fps']:.1f} fps")
                if snap["duration_seconds"] > 0:
                    fraction = min(1., snap["frames_read"]/snap["total_frames"]) if snap["total_frames"] else min(1.,snap["video_second"]/snap["duration_seconds"])
                    st.progress(fraction, text=f"{fraction:.0%} of video · {snap['video_second']/60:.1f}/{snap['duration_seconds']/60:.1f} min")
                elif snap["analyzed_frames"]:
                    st.caption(f"Observed video timestamp: {snap['video_second']:.1f}s")
                if snap["error"]:
                    st.error(snap["error"])
                    if snap.get("source_kind") == "youtube":
                        st.caption("This does not prove the broadcast is offline: YouTube may allow normal playback but refuse server-side frame access.")
                        st.link_button("Open original YouTube video ↗", job.source,
                                       use_container_width=True)
                if snap["status"] in {"starting", "connecting stream", "loading model", "running", "finalizing video"}:
                    if not snap["is_live"]:
                        if st.button("Resume" if snap["paused"] else "Pause", use_container_width=True, key="sr_pause"):
                            job.resume() if snap["paused"] else job.pause()
                            st.rerun(scope="fragment")
                    if st.button("Stop analysis", use_container_width=True, key="sr_stop"):
                        job.stop()
                        st.rerun(scope="fragment")
                if snap["status"] == "connecting stream":
                    st.info("Checking whether YouTube offers a usable video stream to this server...")
                elif snap["status"] == "loading model":
                    st.info("Loading AI model. The video source is accessible at this stage.")
                if snap["status"] in {"completed", "stopped", "ended", "error"}:
                    if st.button("＋ New analysis", use_container_width=True, key="sr_new_job"):
                        st.session_state["video_job"] = None
                        st.rerun()
    if snap and snap.get("source_kind") == "public_live":
        details = get_camera(job.source)
        st.caption(f"Camera credit: {details['operator']} · See agency terms for footage reuse.")
        st.link_button("Agency information & conditions ↗", details["info_url"])
    if snap and snap.get("source_kind") == "youtube" and snap.get("status") != "error":
        with st.expander("Original YouTube live player (independent, not synchronized)"):
            st.video(job.source)
            st.caption("The player and analysis have independent buffers and delays. This is not a frame-accurate synchronized comparison.")
    st.markdown('<div class="sr-footnote">Live = updates while processing. On CPU, AI throughput may be much slower than the broadcast FPS. Provisional detection results are not driving alerts.</div>', unsafe_allow_html=True)


def live_metrics(snap):
    section_header("Scene at a glance", "03 / Live observations, not predicted accidents")
    counts = snap.get("detected_now", {}) if snap else {}
    scene = snap.get("scene", {}) if snap else {}
    metric_cards([
        ("Vehicles in current frame", counts.get("vehicles", 0), "objects", ""),
        ("Pedestrians in current frame", counts.get("people", 0), "objects", ""),
        ("Track IDs observed", snap.get("unique_tracks", 0) if snap else 0, "IDs", ""),
        ("Apparent motion", f"{snap.get('mean_apparent_speed', 0):.1f}" if snap else "—", "px/s", ""),
        ("Image brightness", f"{scene.get('brightness', 0):.0f}" if scene else "—", "0–255", ""),
        ("Image occupancy", f"{scene.get('occupancy_ratio',0)*100:.0f}%" if scene else "—", "box area*", ""),
        ("Image proximity pairs", scene.get("visual_proximity_pairs", 0), "current frame", "warn" if scene.get("visual_proximity_pairs") else ""),
        ("Calibrated speed", f"{snap.get('mean_calibrated_speed',0):.1f}" if snap and snap.get("calibrated_speed_samples") else "—", "km/h est.", ""),
    ])
    st.markdown(
        '<div class="sr-footnote">* Overlapping detection boxes can inflate occupancy. '
        'Close objects in image coordinates do not prove close distances on the road. '
        'Speed is an approximate image-scale estimate only when manual calibration is supplied.</div>',
        unsafe_allow_html=True
    )


def intelligence_view(snap):
    section_header("Scene intelligence", "Signals grounded in recorded frames")
    feature_tiles()
    if snap is None or not snap.get("recent_frames"):
        st.info("Run an analysis to populate charts and diagnostics. Models for potholes, road-surface damage, water, and verified collision risk require specialized training and calibration.")
        return
    frames = pd.DataFrame(snap["recent_frames"])
    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("**Traffic observation timeline**")
            st.line_chart(frames.set_index("video_second")[["vehicles", "people", "traffic_lights", "stop_signs"]],
                          height=270)
            st.caption("Current objects per sampled frame. These are not unique cumulative traffic counts.")
    with right:
        with st.container(border=True):
            st.markdown("**Current image diagnostics**")
            diag = snap.get("scene", {})
            c1, c2 = st.columns(2)
            c1.metric("Brightness /255", diag.get("brightness", "—"))
            c2.metric("Box area / frame", f"{diag.get('occupancy_ratio', 0)*100:.0f}%")
            st.caption("Brightness uses raw image pixels; not a lux meter or certified visibility rating.")
            st.caption("Crowded-image warning: " + ("Yes · heuristic" if diag.get("dense_scene") else "Not triggered"))
            st.caption("Close person/vehicle in image: " + str(diag.get("visual_proximity_pairs", 0)) + " pair(s)")
    section_header("Tracked objects", "Most recent 80 detections, with per-object evidence")
    if snap.get("recent_objects"):
        df = pd.DataFrame(snap["recent_objects"]).iloc[::-1]
        selected = ["video_second", "track_id", "class", "confidence", "direction", "image_motion_px_s", "calibrated_speed_kmh"]
        available = [c for c in selected if c in df.columns]
        st.dataframe(df[available], hide_index=True, use_container_width=True,
                     column_config={
                         "video_second": st.column_config.NumberColumn("Time (s)", format="%.1f"),
                         "track_id": "Track ID",
                         "class": "Object",
                         "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
                         "direction": "Screen direction",
                         "image_motion_px_s": st.column_config.NumberColumn("Motion (px/s)", format="%.1f"),
                         "calibrated_speed_kmh": st.column_config.NumberColumn("Speed estimate (km/h)", format="%.1f"),
                     })
        st.caption("A tracked ID may change after occlusion. Screen direction and pixel motion must not be interpreted as actual road heading or speed.")
    else:
        st.caption("No tracked objects recorded yet.")


def events_view(snap):
    section_header("Evidence timeline", "Observed conditions; not automated accident claims")
    if snap is None or not snap.get("recent_events"):
        st.markdown('<div class="sr-empty" style="min-height:190px"><div class="sr-empty-icon">✓</div>'
                    '<strong>No diagnostic events yet</strong><p>Only specific experimental heuristics are recorded. '
                    'No event does not mean the road is safe.</p></div>', unsafe_allow_html=True)
        return
    for e in reversed(snap["recent_events"][-30:]):
        glyph = "○" if e["level"] == "observe" else "!"
        st.markdown(
            '<div class="sr-event"><div class="sr-event-icon">' + glyph + '</div>'
            '<div><strong>' + escape(e["title"]) + '</strong><p>' +
            escape(e["description"]) + '</p></div><time>' +
            f'{e["video_second"]:.1f}s' + '</time></div>', unsafe_allow_html=True
        )


def exports_view(job, snap, hosted):
    section_header("Reports & exports", "Download machine-readable evidence after the run")
    if job is None:
        st.info("Analyze a video first. Frame-level observations and diagnostic events are written incrementally to CSV.")
        return
    if snap["status"] in {"running", "starting", "connecting stream", "loading model"}:
        st.info("This session is live. Counts and events update in Workspace/Intelligence. The complete files become downloadable when the run stops.")
        return
    if snap["status"] == "error":
        st.warning("The session encountered an error. Any partial CSV files are unverified.")
    st.markdown("**Executive observation summary**")
    st.caption(
        f"Source: {snap['label']} · {snap['analyzed_frames']:,} frames analyzed · "
        f"Max visible vehicles in one frame: {snap['max_vehicles']} · "
        f"Max visible people in one frame: {snap['max_people']} · "
        f"{snap['total_events']} experimental diagnostic events"
    )
    st.caption(
        "No reliable accident probability or real-world speed is inferred without validated "
        "camera geometry and a tested risk model."
    )
    report = {
        "version": "3.0-research", "job_id": job.id, "source": snap["label"],
        "status": snap["status"], "partial_error": snap.get("error") or None,
        "analyzed_frames": snap["analyzed_frames"], "last_video_second": snap["video_second"],
        "max_visible_vehicles": snap["max_vehicles"],
        "max_visible_pedestrians": snap["max_people"],
        "track_ids_observed": snap["unique_tracks"],
        "sampled_frame_class_totals": snap.get("detected_class_totals", {}),
        "frames_with_detected_objects": snap.get("detected_frames", 0),
        "source_kind": snap.get("source_kind", "file"),
        "mean_apparent_motion_px_s": round(snap.get("mean_apparent_speed", 0), 2),
        "mean_calibrated_speed_kmh": (
            round(snap.get("mean_calibrated_speed", 0), 2)
            if snap.get("calibrated_speed_samples") else None
        ),
        "calibration_note": "Uniform m/pixel scale; not perspective corrected or certified speed.",
        "scene_last_frame": snap.get("scene", {}),
        "total_diagnostic_events": snap["total_events"],
        "recent_events": snap.get("recent_events", []),
        "limits": [
            "Object IDs may change after occlusion.",
            "Proximity is in image pixels, not real-world distances.",
            "No validated accident prediction, pothole model or water detection.",
            "Counts refer to sampled frames, not guaranteed unique pass-through counts."
        ]
    }
    st.download_button(
        "Download structured research summary (JSON) ↓",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="smart-road-report.json", mime="application/json",
        key="sr_summary_json"
    )
    files = [
        (job.summary_file, "Frame observations", "video-frame-counts.csv"),
        (job.objects_file, "Object trajectories and motion", "object-observations.csv"),
        (job.events_file, "Image-scene diagnostic events", "scene-events.csv"),
        (job.video_file, "Annotated video", "tracked-video.mp4")
    ]
    for path, label, basename in files:
        if not path.exists() or not path.stat().st_size:
            continue
        mb = path.stat().st_size / (1024 * 1024)
        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown("**" + label + "**")
                st.caption(f"{path.name} · {mb:.2f} MB")
            with c2:
                if mb <= 35:
                    st.download_button("Download ↓", path.read_bytes(), file_name=basename,
                                       mime="video/mp4" if path.suffix == ".mp4" else "text/csv",
                                       use_container_width=True, key="sr_download_" + path.name)
                else:
                    st.caption("Large file; use local processing for reliable exports.")
    st.caption("Cloud results live temporarily on the remote app instance, not your PC. Download your data promptly; it may disappear when the server restarts." if hosted else "Local results are saved under outputs/ and are not automatically cleaned up.")


def video_tab():
    apply_theme()
    hosted = os.environ.get("SMART_ROAD_HOSTED", "0") == "1"
    job = st.session_state.get("video_job")
    snap = job.snapshot() if job else None
    active = bool(snap and snap["status"] in {"starting", "connecting stream", "loading model", "running", "finalizing video"})
    brand(hosted, snap)
    if hosted:
        st.caption("CLOUD RESEARCH PREVIEW · Shared server, no accounts or privacy guarantees. Upload only non-sensitive, permitted video. Long jobs can be interrupted by hosting limits.")
    else:
        st.caption("LOCAL RESEARCH WORKSPACE · For long recordings or connected PC cameras, use this locally with sufficient storage.")

    pages = ["Workspace", "Intelligence", "Events & reports"]
    selection = st.radio("Section", pages, horizontal=True, key="sr_main_tab",
                         label_visibility="collapsed")
    if selection == "Workspace":
        if not active and not (snap and snap["status"] in {"completed", "stopped", "ended", "error"}):
            source_and_settings(hosted, active)

        @st.fragment(run_every=1.0 if active else None)
        def monitor():
            current = st.session_state.get("video_job")
            state = current.snapshot() if current else None
            if state and state["status"] in {"completed", "stopped", "ended", "error"}:
                if st.session_state.get("sr_last_finished_job") != current.id:
                    st.session_state["sr_last_finished_job"] = current.id
                    st.rerun(scope="app")
            if state and state["status"] in {"completed", "stopped", "ended"}:
                st.success("Video analysis completed. Detailed, playable results are below.")
            video_stage(state, current)
            live_metrics(state)
            if state and state["analyzed_frames"]:
                st.markdown("### Results overview")
                totals = state.get("detected_class_totals", {})
                st.caption(
                    f"Frames with detections: {state.get('detected_frames', 0):,} of "
                    f"{state['analyzed_frames']:,} analyzed · "
                    f"Peak vehicles: {state['max_vehicles']} / frame · "
                    f"Peak pedestrians: {state['max_people']} / frame · "
                    f"Image-condition observations: {state['total_events']}"
                )
                if totals:
                    summary = pd.DataFrame(
                        [{"Object type": key, "Sampled-frame detections": val}
                         for key, val in sorted(totals.items(), key=lambda entry: -entry[1])]
                    )
                    st.dataframe(summary, hide_index=True, use_container_width=True)
                    st.caption("These totals count repeated detections across frames, NOT distinct vehicles passing the camera.")
                else:
                    st.info("No objects met the selected model and confidence threshold. Try a higher-quality camera angle or lower the threshold and re-run.")
                if state.get("recent_frames"):
                    df = pd.DataFrame(state["recent_frames"])
                    st.line_chart(df.set_index("video_second")[["vehicles", "people"]],
                                  height=210)
                    st.caption("Latest sampled-frame counts. Navigate to Intelligence for detailed tracks and Events & reports for exports.")
        monitor()
        # Final report stays on the SAME Workspace page; no navigation required.
        current = st.session_state.get("video_job")
        final_state = current.snapshot() if current else None
        if final_state and final_state["status"] in {"completed", "stopped", "ended"} and final_state["analyzed_frames"]:
            results_page(current, final_state, hosted)
    elif selection == "Intelligence":
        @st.fragment(run_every=1.5 if active else None)
        def intelligence_monitor():
            current = st.session_state.get("video_job")
            intelligence_view(current.snapshot() if current else None)
        intelligence_monitor()
    else:
        @st.fragment(run_every=2.0 if active else None)
        def reporting_monitor():
            current = st.session_state.get("video_job")
            current_state = current.snapshot() if current else None
            events_view(current_state)
            exports_view(current, current_state, hosted)
        reporting_monitor()
    st.divider()
    st.caption("SMART ROAD AI · Research prototype · Pixel-based findings are provisional. Do not use these results as real-time driving alerts, speed enforcement, or verified collision predictions.")
