"""A single approachable finished analysis, hiding research configuration."""
from __future__ import annotations
import json
import csv
import streamlit as st
import pandas as pd
from road_advice import road_report


@st.cache_data(show_spinner=False,max_entries=12,ttl=1800)
def _cached_road_report(evidence_json,source,path,size,mtime_ns):
    return road_report(json.loads(evidence_json),source,path)


@st.cache_data(show_spinner=False,max_entries=12,ttl=1800)
def _cached_interactions(path,width,height,size,mtime_ns):
    from safety_interactions import find_interactions
    return find_interactions(path,width,height)


@st.cache_data(show_spinner=False,max_entries=12,ttl=1800)
def _cached_stationary(path,width,height,size,mtime_ns):
    from source_scene_evidence import stationary_review_candidates
    return stationary_review_candidates(path,width,height)


def _objects_stamp(path):
    from pathlib import Path
    f=Path(path)
    if not f.is_file():return (0,0)
    stat=f.stat()
    return (stat.st_size,stat.st_mtime_ns)


def _summary_curve(path,max_items=400):
    if not path.is_file():return None
    # Bounded-memory two-pass downsampling even for hours of footage.
    with path.open("r",encoding="utf-8-sig",newline="") as stream:
        length=sum(1 for _ in csv.DictReader(stream))
    if not length:return None
    step=max(1,(length+max_items-1)//max_items)
    data=[]
    with path.open("r",encoding="utf-8-sig",newline="") as stream:
        for i,row in enumerate(csv.DictReader(stream)):
            if i%step:continue
            try:data.append({"Time (seconds)":float(row["video_second"]),
                             "Vehicles visible":int(row["vehicles"]),
                             "People visible":int(row["people"])})
            except (KeyError,ValueError):continue
    return pd.DataFrame(data).set_index("Time (seconds)") if data else None


def show_results(job,snap):
    evidence=snap.get("evidence") or {}
    crossings=snap.get("crossings") or {}
    objects_path=getattr(job,"objects_file",None)
    source_size,source_mtime=_objects_stamp(objects_path)
    story=_cached_road_report(json.dumps(evidence,sort_keys=True,default=str),
                              snap.get("label","video"),str(objects_path) if objects_path else None,
                              source_size,source_mtime)
    st.markdown("## Your road, understood.")
    st.caption("Results are based on detected objects across the uploaded video—not assumptions about an unseen accident.")

    total=int(crossings.get("total_passed",0))
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Vehicles passed the line",total,help="Only tracked vehicles that crossed the chosen counting line, not all vehicles ever seen.")
    m2.metric("Vehicles at peak",snap.get("max_vehicles",0),help="Largest number visible in a sampled frame.")
    m3.metric("Frames analyzed",f"{snap.get('analyzed_frames',0):,}")
    m4.metric("Frames with detections",
              f"{snap.get('detected_frames',0)}/{max(1,snap.get('analyzed_frames',0))}")
    if snap.get("detail_scans_attempted",0):
        st.caption(
            f"Additional small-object analysis: {snap['detail_scans_attempted']} "
            f"focused scans found {snap.get('additional_detail_candidate_boxes',0)} "
            "extra detection candidate boxes after duplicate filtering. "
            "These are not verified new vehicles; false positives remain possible."
        )
    if snap.get("analyzed_frames",0) >= 10 and snap.get("detected_frames",0)<.40*snap["analyzed_frames"]:
        st.warning("Detection confidence is low for this footage: objects were not found in most sampled frames. The number of vehicles is likely an undercount. Do not treat these measurements as ground truth.")
    with st.container(border=True):
        st.markdown("### What the AI observed")
        st.write(story["summary"])
        st.caption("Road context: "+story["context"]["label"]+" · "+story["context"]["basis"])
        st.caption("Cars crossing the yellow line, objects visible simultaneously and tracking IDs are different counts.")

    st.markdown("### Your analyzed video")
    if snap.get("video_ready") and job.video_file.is_file():
        st.video(str(job.video_file),format="video/mp4")
        st.caption("Overlay video contains sampled frames spread over the original timeline. YOLO annotations are model estimates.")
        if job.video_file.stat().st_size<120*1024*1024:
            st.download_button("Download analyzed video",job.video_file.read_bytes(),
                               file_name="smart-road-analysis.mp4",mime="video/mp4")
    elif snap.get("video_export_error"):
        st.error("Analysis finished, but the playable video could not be created: "+snap["video_export_error"])
    elif snap.get("best_preview_jpeg"):
        st.image(snap["best_preview_jpeg"],caption="Analyzed video frame",use_container_width=True)

    st.markdown("### Traffic through time")
    curve=_summary_curve(job.summary_file)
    if curve is not None:
        st.line_chart(curve,height=240,use_container_width=True)
    st.caption("Shows visible objects in sampled frames, not how many distinct cars passed.")

    # Evidence-linked, timestamped review events (not verified collisions).
    interaction_events=_cached_interactions(
        str(objects_path) if objects_path else None,
        snap.get("frame_width",0),snap.get("frame_height",0),
        source_size,source_mtime
    )
    from road_scenarios import candidate_site_review
    interaction_study=candidate_site_review(interaction_events,evidence)
    if interaction_study:
        story["recommendations"].insert(0,interaction_study)
    st.markdown("### Events worth reviewing")
    if interaction_events:
        st.write(f"{len(interaction_events)} time-localized pedestrian/vehicle review candidate(s). These are image-plane proximity observations — NOT confirmed accidents, near misses, or unauthorized crossings.")
        for i,event in enumerate(interaction_events[:8],1):
            with st.container(border=True):
                st.markdown(f"**{i}. Possible shared-space interaction · {event['video_second']:.1f}s**")
                st.caption(f"Sampled window {event['start_second']:.1f}–{event['end_second']:.1f}s · {event['frame_count']} supporting frames · IDs {event['person_track']} and {event['vehicle_track']}")
                st.write(event["explanation"])
                if st.button(f"Watch supporting video at {event['video_second']:.1f}s",
                             key=f"review_event_{job.id}_{i}"):
                    st.session_state["review_timestamp_"+job.id]=max(0,int(event["video_second"]-2))
        chosen_time=st.session_state.get("review_timestamp_"+job.id)
        if chosen_time is not None:
            from video_comparison import source_video_path
            original=source_video_path(job)
            proxy=job.folder / "comparison_original.mp4"
            if proxy.is_file() and proxy.stat().st_size>100:
                st.video(str(proxy),start_time=chosen_time,format="video/mp4")
                st.caption("Unmodified browser-compatible source-video copy, starting near the selected observation.")
            elif original and original.suffix.lower()==".mp4":
                st.video(str(original),start_time=chosen_time,format="video/mp4")
                st.caption("Original footage starting near the selected observation.")
            elif job.video_file.is_file():
                st.video(str(job.video_file),start_time=chosen_time,format="video/mp4")
                st.caption("Analyzed-video export with AI annotations, starting near the selected observation. This is not the unmodified original.")
            else:
                st.warning("This event has a valid timestamp, but no browser-playable video preview is available.")
    else:
        st.info("No sustained pedestrian–vehicle image-overlap was established from the tracked frames. This does not mean the road is safe; the AI may have missed objects or the video may lack enough coverage.")

    from source_scene_evidence import review_moments
    from source_scene_view import display_source_review
    stationary_events=_cached_stationary(
        str(objects_path) if objects_path else None,
        snap.get("frame_width",0),snap.get("frame_height",0),
        source_size,source_mtime
    )
    review_items=review_moments(interaction_events,stationary_events)
    if stationary_events:
        item=stationary_events[0]
        story["recommendations"].insert(0,{
            "id":"stationary_vehicle_review",
            "title":"Review possible stopping and curbside traffic activity",
            "evidence":(
                f"A {item['class']} track stayed near the same image point "
                f"around {item['video_second']:.1f}s "
                f"({item['frame_count']} supporting samples); "
                "physical stationary status is not verified."
            ),
            "reason":"Repeated low image motion can indicate queuing or stopping, "
                     "but camera perspective may also make distant vehicles look slow.",
            "action":item["review_action"],
            "verify":"Watch the exact source moment and survey roadway ownership, "
                     "stopping rules, traffic direction and curb space before changing it.",
            "priority":"Review","expected_benefit":"Not measured",
            "confidence":"Recorded tracker image motion, needs manual verification",
            "simulation_option":"inspection",
        })
    st.markdown("### This exact road · Evidence and potential improvements")
    st.caption("The scene on both sides is taken from YOUR recorded road; only the "
               "evidence location is outlined. No invented highway, yellow circles, "
               "simulated cars, or unverified construction.")
    display_source_review(job,review_items)

    st.markdown("### Recommendations supported by this footage")
    st.caption("Only video-backed review suggestions appear here. No automatic pedestrian crossing or speed limit is proposed without supporting field evidence.")
    for i,r in enumerate(story["recommendations"],1):
        with st.container(border=True):
            st.markdown(f"#### {i}. {r['title']}")
            st.markdown("**What we actually measured**")
            st.write(r["evidence"])
            st.markdown("**Why it matters**")
            st.write(r["reason"])
            st.markdown("**Suggested next step**")
            st.write(r["action"])
            st.caption("Expected benefit: "+r["expected_benefit"])
            st.caption("Evidence status: "+r["confidence"]+" · Priority: "+r["priority"])
            st.caption("Check before construction: "+r["verify"])

    st.markdown("### Explore the road in interactive 3D")
    with st.expander("Improve 3D alignment with actual measured road dimensions (optional)",
                     expanded=False):
        from road_calibration_ui import show_calibration
        show_calibration(job,snap)

    surveyed=st.session_state.get("surveyed_road_"+job.id)
    if surveyed:
        from traffic_geometry import RoadCalibration
        cal_data=surveyed["calibration"]
        calibration=RoadCalibration(
            tuple(tuple(p) for p in cal_data["points"]),
            cal_data["width_m"],cal_data["length_m"])
        st.success("A surveyed source-camera road patch is available. The primary 3D viewer can now use the actual recorded road image and measured patch geometry instead of the generic example.")
        if st.button("Open camera-aligned 3D scene for this road",
                     type="primary",use_container_width=True,
                     key="road_aligned_open_"+job.id):
            st.session_state["road_aligned_active_"+job.id]=True
        if st.session_state.get("road_aligned_active_"+job.id):
            from calibrated_scene_view import show_surveyed_scene
            show_surveyed_scene(job,snap,calibration,
                                surveyed["camera_fov_deg"])
        st.caption("The camera-aligned scene uses only the calibrated flat road patch. Surrounding 3D structures are not invented. The independent fifth-point check determines whether the geometry has external validation.")
    else:
        st.info("Source-specific, metrically aligned 3D needs measured road reference geometry. Without it, only an explicitly labeled hypothetical traffic-control scenario can be shown.")
    # Deliberately do NOT render the generic signal simulator below a real
    # urban-road recording. The old independent demo was mistaken for an AI
    # reconstruction and could trigger unnecessary expensive CPU work.
    # Its library code remains available for explicitly surveyed concepts.
    if not surveyed:
        st.caption("A source-matched 3D change needs checked road geometry. "
                   "The previous unrelated straight-highway demo is not shown as "
                   "an improvement to your urban road.")

    with st.expander("Measure the AI's accuracy against labeled frames (optional)"):
        st.write("Actual precision, recall and F1 require manually labeled ground-truth boxes. Unlabeled video frames are excluded completely.")
        st.download_button("Download labeling template",
                           "frame_number,class,x1,y1,x2,y2\n",
                           file_name="road-ground-truth-template.csv",
                           mime="text/csv",key="truth_template_"+job.id)
        st.caption("Add one row per ground-truth object. Use class 'none' for a checked frame containing no relevant objects. Use pixel coordinates from the original video and matching frame_number values.")
        labels=st.file_uploader("Upload manually checked frame annotations (CSV)",
                                type=["csv"],key="truth_upload_"+job.id)
        if labels is not None:
            from detection_qa import evaluate_detections
            try:
                assessment=evaluate_detections(labels.getvalue(),job.objects_file)
                st.success(f"Evaluated {assessment['annotated_frames']} labeled video frames at IoU ≥ {assessment['iou_threshold']:.2f}.")
                a,b,c=st.columns(3)
                for col,name in zip((a,b,c),("precision","recall","f1")):
                    value=assessment["overall"][name]
                    col.metric(name.title(),"Not defined" if value is None else f"{value:.1%}")
                st.dataframe([{"class":name,**values}
                              for name,values in assessment["classes"].items()],
                             use_container_width=True,hide_index=True)
                st.caption(assessment["limitations"])
                st.download_button("Download validation summary (JSON)",
                                   json.dumps(assessment,indent=2),
                                   file_name="detection-validation.json",
                                   mime="application/json",key="qa_download_"+job.id)
            except (OSError,ValueError,UnicodeError) as exc:
                st.error("Could not evaluate these annotations: "+str(exc))

    with st.expander("Download data & inspect measurement limits"):
        surveyed=st.session_state.get("surveyed_road_"+job.id)
        report={"source":snap["label"],"status":snap["status"],
                "crossings":crossings,"evidence":evidence,
                "recommendations":story["recommendations"],
                "review_needed":"Single-camera AI can miss vehicles and cannot establish metric speed or 3D dimensions without calibration.",
                "context":story["context"],"kinematic_evidence":story["measurements"],
                "interaction_review_candidates":interaction_events,
                "surveyed_ground_measurements": surveyed["tracks_report"] if surveyed else None,
                "surveyed_ground_geometry": surveyed["calibration"] if surveyed else None,
                "independent_ground_checkpoint": surveyed.get("independent_checkpoint") if surveyed else None,
                "calibrated_ground_interaction_review": surveyed.get("calibrated_interaction_review") if surveyed else None,
                "ground_measurements_validation": (
                    "independent surveyed checkpoint passed"
                    if surveyed and (surveyed.get("independent_checkpoint") or {}).get("status")=="independently_checked"
                    else "provisional / not independently checked"
                )}
        from road_report_pdf import build_road_pdf
        try:
            pdf_bytes=build_road_pdf(
                snap,story,interaction_events,
                st.session_state.get("control_"+job.id+"_results"),
                surveyed
            )
            st.download_button("Download professional road review (PDF)",pdf_bytes,
                               file_name="smart-road-evidence-review.pdf",
                               mime="application/pdf",key="pdf_report_"+job.id)
        except (ValueError,TypeError,KeyError,OSError) as error:
            st.warning("PDF report couldn't be generated: "+str(error))
        st.download_button("Full report (JSON)",json.dumps(report,ensure_ascii=False,indent=2),
                           file_name="road-report.json",mime="application/json")
        for path in (job.objects_file,job.crossings_file,job.summary_file,job.events_file):
            if path.is_file() and path.stat().st_size<80*1024*1024:
                st.download_button(path.name,path.read_bytes(),file_name=path.name,
                                   mime="text/csv",key="clean_csv_"+path.name)
        st.caption("Evidence: detector observations and image-plane tracks. Not evidence of exact speeds, collisions, masses, or guaranteed benefits from a proposed design.")
