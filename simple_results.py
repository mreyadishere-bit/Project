"""A single approachable finished analysis, hiding research configuration."""
from __future__ import annotations
import json
import csv
import streamlit as st
import pandas as pd
from road_advice import road_report


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
    story=road_report(evidence,snap.get("label","video"),getattr(job,"objects_file",None))
    st.markdown("## Your road, understood.")
    st.caption("Results are based on detected objects across the uploaded video—not assumptions about an unseen accident.")

    total=int(crossings.get("total_passed",0))
    m1,m2,m3,m4=st.columns(4)
    m1.metric("Vehicles passed the line",total,help="Only tracked vehicles that crossed the chosen counting line, not all vehicles ever seen.")
    m2.metric("Vehicles at peak",snap.get("max_vehicles",0),help="Largest number visible in a sampled frame.")
    m3.metric("Frames analyzed",f"{snap.get('analyzed_frames',0):,}")
    m4.metric("Frames with detections",
              f"{snap.get('detected_frames',0)}/{max(1,snap.get('analyzed_frames',0))}")
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
    from safety_interactions import find_interactions
    interaction_events=find_interactions(
        getattr(job,"objects_file",None),
        snap.get("frame_width",0),snap.get("frame_height",0)
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

    st.markdown("### Explore a working 3D traffic-control concept")
    st.caption("The original video stays real; the new 3D scenario follows its own hypothetical signal schedule because an intervention changes traffic timing. Vehicles stop and start, pedestrians wait, then cross on WALK.")
    if st.button("Generate interactive 3D crossing & signal simulation",type="primary",
                 use_container_width=True,key="control_sim_"+job.id):
        st.session_state["control_sim_active_"+job.id]=True
    if st.session_state.get("control_sim_active_"+job.id):
        from traffic_control_view import show_concept
        show_concept(job,snap,interaction_events,key="control_"+job.id)

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
        report={"source":snap["label"],"status":snap["status"],
                "crossings":crossings,"evidence":evidence,
                "recommendations":story["recommendations"],
                "review_needed":"Single-camera AI can miss vehicles and cannot establish metric speed or 3D dimensions without calibration.",
                "context":story["context"],"kinematic_evidence":story["measurements"],
                "interaction_review_candidates":interaction_events}
        from road_report_pdf import build_road_pdf
        try:
            pdf_bytes=build_road_pdf(
                snap,story,interaction_events,
                st.session_state.get("control_"+job.id+"_results")
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
