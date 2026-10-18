"""Dr. Traffic | a minimal, evidence-first traffic review studio.

Primary website entrypoint. Legacy Smart Road modules remain recoverable from
the dated backup branch; this app intentionally does not mount that interface.
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
import shutil
import tempfile
import uuid

import streamlit as st

from dr_traffic_engine import ReviewSettings, analyze_video, serialise_json
from dr_traffic_voice import transcribe_voice

st.set_page_config(
    page_title="Dr. Traffic | AI Traffic Review",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root{--dt-bg:#f6f8fc;--dt-ink:#12243d;--dt-muted:#718199;--dt-line:#e4ebf4;--dt-blue:#2563df}
html,body,[data-testid="stApp"]{font-family:'DM Sans',system-ui,sans-serif}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 5% 0%,#eaf0ff 0,transparent 34%),var(--dt-bg)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stDecoration"]{display:none}
.block-container{max-width:1240px;padding-top:1rem;padding-bottom:5rem}
h1,h2,h3{letter-spacing:-.04em!important;color:var(--dt-ink)!important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:20px!important;border:1px solid var(--dt-line)!important;background:#fff!important;box-shadow:0 6px 22px #14294506}
.stButton button{border-radius:12px!important;font-weight:700!important;min-height:44px!important}
.stButton button[kind="primary"]{background:#2563df!important;border-color:#2563df!important}
[data-testid="stFileUploaderDropzone"]{background:#f8faff;border-radius:16px;border:1px dashed #b1c5ef}
[data-testid="stMetric"]{border:1px solid var(--dt-line);background:#fff;border-radius:16px;padding:18px 16px}
[data-testid="stTabs"] button{font-weight:700}
.dt-top{display:flex;justify-content:space-between;gap:18px;align-items:center;padding:15px 0 22px;border-bottom:1px solid var(--dt-line);margin-bottom:26px}
.dt-mark{height:39px;width:39px;border-radius:13px;background:#1e4dc1;display:grid;place-items:center;color:white;font-weight:800;font-size:21px}
.dt-name{font-size:18px;letter-spacing:-.045em;font-weight:800;color:#10243e}
.dt-sub{font-size:11px;font-weight:700;letter-spacing:.12em;color:#7385a0;text-transform:uppercase}
.dt-status{background:#eaf8f1;color:#18734e;border:1px solid #d3efe0;font-size:11px;font-weight:700;padding:8px 13px;border-radius:99px}
.dt-hero{border:1px solid #d9e5f7;background:linear-gradient(117deg,#112c57,#2351a1 75%,#306ace);padding:clamp(25px,4.5vw,48px);border-radius:23px;color:#dce8ff;margin:0 0 25px;box-shadow:0 12px 32px #1b376013}
.dt-kicker{font-size:11px;letter-spacing:.17em;font-weight:800;color:#b8cefc;margin-bottom:12px}
.dt-hero h1{color:white!important;font-size:clamp(2rem,4.5vw,3.3rem)!important;margin:0 0 13px;line-height:1.1;max-width:850px}
.dt-hero p{margin:0;line-height:1.8;color:#d6e4ff;font-size:14px;max-width:720px}
.dt-section{margin:23px 0 13px}
.dt-eyebrow{color:#4477c6;text-transform:uppercase;letter-spacing:.15em;font-size:10px;font-weight:800}
.dt-section h3{font-size:23px;margin:7px 0 5px}
.dt-section p{color:#72829a;font-size:12px;line-height:1.7;margin:0}
.dt-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px;margin:16px 0 24px}
.dt-stat{background:#fff;padding:20px;border:1px solid var(--dt-line);border-radius:18px;min-width:0}
.dt-stat .label{color:#76859a;font-size:11px;font-weight:700}.dt-stat .number{font-size:29px;font-weight:800;color:#142745;letter-spacing:-.06em;margin:7px 0}
.dt-stat .description{color:#8b99ab;font-size:10px;line-height:1.5}
.dt-card{border:1px solid var(--dt-line);background:#fff;border-radius:18px;padding:22px;margin:10px 0}
.dt-card[data-tone="review"]{border-left:4px solid #e9a84b}
.dt-card[data-tone="observation"]{border-left:4px solid #6f91c6}
.dt-card-title{font-weight:800;font-size:16px;color:#1c2e48;letter-spacing:-.025em}
.dt-card p{font-size:12px;line-height:1.7;color:#66768e;margin:10px 0}
.dt-card .meta{font-size:11px;color:#7e8da4}
.dt-pill{background:#fff2df;color:#975d15;font-size:10px;font-weight:800;padding:6px 11px;border-radius:99px;display:inline-block;margin-bottom:12px}
.dt-pill[data-tone="observation"]{background:#ebf2ff;color:#365fa2}
.dt-footnote{padding:15px 18px;border:1px solid #d9e3f2;background:#f0f5fc;border-radius:14px;color:#4f6380;font-size:12px;line-height:1.75}
.dt-flow{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.dt-step{background:white;border:1px solid var(--dt-line);border-radius:14px;padding:13px;text-align:center}
.dt-step strong{display:block;font-size:12px;color:#264164}
.dt-step small{display:block;font-size:10px;color:#8794a4;margin-top:5px}
@media(max-width:800px){.dt-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.dt-flow{grid-template-columns:repeat(2,minmax(0,1fr))}.dt-status{display:none}}
@media(max-width:440px){.block-container{padding-left:1rem;padding-right:1rem}.dt-stat{padding:14px}.dt-stat .number{font-size:24px}}
</style>
"""


def safe(value):
    return escape(str(value), quote=True)


def section(title, caption, eyebrow="ROAD INTELLIGENCE"):
    st.markdown(
        '<div class="dt-section"><div class="dt-eyebrow">' + safe(eyebrow)
        + '</div><h3>' + safe(title) + '</h3><p>' + safe(caption) + '</p></div>',
        unsafe_allow_html=True,
    )


def stat_cards(items):
    cards = []
    for label, value, desc in items:
        cards.append(
            '<div class="dt-stat"><div class="label">' + safe(label)
            + '</div><div class="number">' + safe(value)
            + '</div><div class="description">' + safe(desc) + '</div></div>'
        )
    st.markdown('<div class="dt-metrics">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def event_card(event):
    tone = event.get("severity", "observation")
    if tone not in {"review", "observation"}:
        tone = "observation"
    tag = "Needs verification" if tone == "review" else "Recorded observation"
    st.markdown(
        '<div class="dt-card" data-tone="' + tone + '"><span class="dt-pill" data-tone="' + tone + '">'
        + tag + '</span><div class="dt-card-title">' + safe(event.get("title", "Observation"))
        + '</div><p>' + safe(event.get("evidence", "")) + '</p><div class="meta">'
        + 'At ' + safe(event.get("timestamp_seconds", "—")) + ' s · '
        + safe(event.get("object_type", "vehicle")) + ' · Track '
        + safe(event.get("track_id", "?")) + '</div><p>'
        + safe(event.get("limitations", "")) + '</p></div>',
        unsafe_allow_html=True,
    )


st.markdown(STYLE, unsafe_allow_html=True)
st.markdown(
    '<div class="dt-top"><div style="display:flex;align-items:center;gap:12px">'
    '<div class="dt-mark">D</div><div><div class="dt-name">Dr. Traffic</div>'
    '<div class="dt-sub">AI traffic evidence studio</div></div></div>'
    '<span class="dt-status">● Research preview</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="dt-hero"><div class="dt-kicker">TRAFFIC INTELLIGENCE REIMAGINED</div>'
    '<h1>Spot the moment.<br>Understand the road.</h1>'
    '<p>Upload a road recording, track vehicles, inspect important moments and export '
    'traceable evidence for human review. A clean workflow without technical complexity.</p></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="dt-footnote">This is an educational video-review system. '
    'It does not issue fines, identify vehicle owners or independently verify '
    'a traffic-law violation. No real speed, distance or depth is measured.</div>',
    unsafe_allow_html=True,
)

if "dt_report" not in st.session_state:
    st.session_state.dt_report = None
if "dt_evidence" not in st.session_state:
    st.session_state.dt_evidence = {}
if "dt_video_path" not in st.session_state:
    st.session_state.dt_video_path = None

if st.session_state.dt_report is None:
    section("Start a new review", "One recording is all you need. Analysis runs on the server; no webcam permissions required.", "YOUR WORKSPACE")
    a, b = st.columns([1.85, 1], gap="large")
    with a:
        with st.container(border=True):
            st.markdown("#### Add a road recording")
            upload = st.file_uploader(
                "Choose a video", type=["mp4", "mov", "avi", "mkv", "m4v"],
                help="Use footage that you have permission to analyze. Prefer a fixed camera.",
            )
            voice_upload = st.file_uploader(
                "Optional spoken instruction (Whisper · WAV, MP3, M4A, OGG)",
                type=["wav", "mp3", "m4a", "ogg"], key="dt_voice",
                help="Whisper is an optional local dependency. Voice never proves a violation.",
            )
            if upload:
                st.caption(f"{upload.name} · {upload.size/1048576:.1f} MB")
            st.markdown("**What gets checked**")
            st.caption("Vehicles, pedestrians, stable tracking IDs and crossings of a visible review line.")
            with st.expander("Advanced · Check traffic signal timing", expanded=False):
                st.caption(
                    "Enable only when you verified that the signal visible to the tracked "
                    "vehicles was red throughout the entered interval. This does not verify legal guilt."
                )
                red = st.checkbox("I manually verified a red signal in this footage", value=False)
                l, r = st.columns(2)
                with l:
                    red_start = st.number_input("Red phase starts (s)", min_value=0.0, value=0.0, step=0.5, disabled=not red)
                with r:
                    red_end = st.number_input("Red phase ends (s)", min_value=0.0, value=5.0, step=0.5, disabled=not red)
                line = st.slider("Image review-line height", 5, 95, 58, step=1, help="Percentage down the video. Must be positioned on the visible stop line.")
                direction = st.selectbox("Vehicle motion across line", ["down", "up"], help="Down means moving toward the bottom of the image.")
            with st.expander("Optional · Detection performance"):
                tracker = st.selectbox("Tracking algorithm", ["ByteTrack", "BoT-SORT"], index=0)
                detector = st.selectbox("AI model", ["Fast · YOLO26 Nano", "Higher detail · YOLO26 Small"], index=0)
                scan_rate = st.select_slider("Sampled frames per second", options=[1, 2, 3, 5], value=3)
            if st.button("Analyze traffic video →", type="primary", use_container_width=True, disabled=upload is None):
                if upload is None:
                    st.warning("Please add a video.")
                else:
                    config = ReviewSettings(
                        model_name="yolo26n.pt" if detector.startswith("Fast") else "yolo26s.pt",
                        tracker="bytetrack.yaml" if tracker == "ByteTrack" else "botsort.yaml",
                        analysis_fps=scan_rate,
                        stop_line_y=line / 100,
                        direction=direction,
                        manually_verified_red=red,
                        red_start=red_start,
                        red_end=red_end,
                    )
                    try:
                        config.validate()
                        folder = Path(tempfile.mkdtemp(prefix="drtraffic_"))
                        suffix = Path(upload.name).suffix.lower()
                        video_path = folder / ("source" + suffix)
                        upload.seek(0)
                        with video_path.open("wb") as handle:
                            shutil.copyfileobj(upload, handle, length=1024 * 1024)
                        status = st.empty()
                        bar = st.progress(0, text="Preparing AI models…")

                        def show_progress(value, label):
                            bar.progress(min(1.0, max(0.0, value)), text=label)

                        with st.spinner("Detecting and tracking vehicles across the recording…"):
                            report, evidence = analyze_video(video_path, settings=config, progress=show_progress)
                        if voice_upload is not None:
                            voice_path = folder / ("voice" + Path(voice_upload.name).suffix.lower())
                            voice_upload.seek(0)
                            with voice_path.open("wb") as handle:
                                shutil.copyfileobj(voice_upload, handle, length=1024 * 1024)
                            try:
                                with st.spinner("Transcribing the optional voice note…"):
                                    report["voice_note"] = transcribe_voice(voice_path)
                            except (RuntimeError, ValueError, OSError) as audio_error:
                                report["voice_note"] = {
                                    "status": "unavailable",
                                    "explanation": str(audio_error),
                                    "synchronized_to_video": False,
                                }
                            finally:
                                voice_path.unlink(missing_ok=True)
                        st.session_state.dt_report = report
                        st.session_state.dt_evidence = evidence
                        st.session_state.dt_video_path = str(video_path)
                        st.rerun()
                    except (Exception) as exc:
                        st.error(f"Could not complete this video review: {exc}")
    with b:
        with st.container(border=True):
            st.markdown("#### How it works")
            st.markdown("**01 · Detect**")
            st.caption("YOLO locates road users in sampled frames.")
            st.markdown("**02 · Track**")
            st.caption("ByteTrack / BoT-SORT associates vehicles over time.")
            st.markdown("**03 · Review**")
            st.caption("Timestamped candidate events are shown with visual evidence.")
            st.markdown("**04 · Export**")
            st.caption("Download structured, transparent JSON findings.")
        with st.container(border=True):
            st.markdown("#### Additional modules")
            st.caption("Voice-command transcription, Egyptian plate OCR, dedicated litter-event detection and vision-language review require separately validated models. They are not falsely reported as live today.")
else:
    report = st.session_state.dt_report
    events = report.get("events", [])
    coverage = report.get("coverage", {})
    metrics = report.get("metrics", {})
    section("Your review is ready", "See exactly what was detected, check source evidence and export findings.", "COMPLETED ANALYSIS")
    stat_cards([
        ("Sampled frames", f"{coverage.get('sampled_frames',0):,}", "Frames actually analyzed"),
        ("Peak visible vehicles", metrics.get("peak_vehicles_in_sample", 0), "In one analyzed frame"),
        ("Moments to review", len(events), "Not verified legal violations"),
        ("Frames with objects", f"{coverage.get('frames_with_detections',0):,}", "Detection can miss objects"),
    ])
    overview_tab, cases_tab, source_tab, report_tab = st.tabs(
        ["Overview", f"Review moments · {len(events)}", "Source evidence", "Export & limits"]
    )
    with overview_tab:
        with st.container(border=True):
            st.markdown("#### Summary")
            if events:
                suspects = sum(x.get("type") == "possible_red_signal_crossing" for x in events)
                st.write(f"Reviewed {coverage.get('sampled_frames', 0)} sampled frames. "
                         f"Found {len(events)} line-crossing observations, including {suspects} "
                         "crossing(s) during a user-marked red-signal interval.")
            else:
                st.write("No tracked vehicle crossing met the current line-review rules. "
                         "This does not establish that there were no violations.")
            st.caption("The source video's original frames were sampled. Camera geometry, speed and traffic-light timing have not been independently measured.")
            note = report.get("voice_note")
            if note:
                st.markdown("**Voice note**")
                if note.get("transcript"):
                    st.write(note["transcript"])
                    st.caption("Intent: " + note.get("intent", "general_voice_note") + " · not synchronized with video.")
                else:
                    st.info(note.get("explanation", "Voice transcription is unavailable."))
        section("How the system reached its findings", "Traceable automated processing, with human verification required for legal interpretation.", "TRANSPARENCY")
        st.markdown(
            '<div class="dt-flow"><div class="dt-step"><strong>Object detection</strong><small>YOLO26</small></div>'
            '<div class="dt-step"><strong>Object tracking</strong><small>' + safe(report["tracker"]) + '</small></div>'
            '<div class="dt-step"><strong>Temporal evidence</strong><small>Marked line crossing</small></div>'
            '<div class="dt-step"><strong>Human review</strong><small>Unverified candidate</small></div></div>',
            unsafe_allow_html=True,
        )
    with cases_tab:
        section("Events worth inspecting", "Cards show observed vehicle movements and their limits. Nothing here confirms a traffic-law offence.", "FINDINGS")
        if not events:
            st.info("No line-crossing review candidates found. Check that the review line matches the visible stop line.")
        for idx, event in enumerate(events):
            with st.container(border=True):
                event_card(event)
                if idx in st.session_state.dt_evidence:
                    st.image(st.session_state.dt_evidence[idx], caption=f"Annotated evidence near {event['timestamp_seconds']} s", use_container_width=True)
                st.caption("Footpoint and image-line annotations are not measured physical geometry.")
    with source_tab:
        section("Inspect the original recording", "The original remains available for comparison with timestamped findings.", "SOURCE VIDEO")
        video_path = st.session_state.dt_video_path
        if video_path and Path(video_path).is_file():
            st.video(video_path)
            if events:
                selected = st.selectbox(
                    "Jump to an event", list(range(len(events))),
                    format_func=lambda idx: f"{events[idx]['timestamp_seconds']:.1f}s · {events[idx]['title']}",
                )
                if st.button("Play from this moment"):
                    st.video(video_path, start_time=max(0,int(events[selected]["timestamp_seconds"])-2))
        else:
            st.warning("The source video is no longer available on the server.")
    with report_tab:
        section("Evidence report", "Share structured results without silently upgrading observations into legal facts.", "DOWNLOAD")
        st.download_button(
            "Download findings (JSON)", serialise_json(report),
            file_name="dr-traffic-evidence.json", mime="application/json",
            type="primary", use_container_width=True,
        )
        with st.expander("What this analysis cannot establish"):
            for item in report.get("limitations", []):
                st.markdown("- " + item)
            if coverage.get("observations_truncated"):
                st.warning("The exported detailed observations were capped to keep memory bounded. The summary and detected events are still included.")
        st.caption("Privacy: recordings are analyzed in the running app environment. Do not upload identifiable footage without permission.")
    if st.button("Analyze another video", use_container_width=True):
        old = st.session_state.dt_video_path
        st.session_state.dt_report = None
        st.session_state.dt_evidence = {}
        st.session_state.dt_video_path = None
        if old:
            try:
                shutil.rmtree(Path(old).parent)
            except OSError:
                pass
        st.rerun()
