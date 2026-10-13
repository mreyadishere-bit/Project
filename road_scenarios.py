"""Grounded, simple visual experiments from observed video evidence.

These are transparent visualization scenarios, not AI-certified interventions.
Do not infer nighttime exposure, road markings, or danger from detector boxes.
"""
from __future__ import annotations


def make_scenarios(report: dict, evidence: dict) -> dict:
    pct = evidence.get("percent_of_sampled_frames", {}) or {}
    avgs = evidence.get("averages_per_frame", {}) or {}
    frames = int(evidence.get("analyzed_frames", 0) or 0)
    has_traffic = float(pct.get("vehicles", 0) or 0) >= 8
    dark_pct = float(pct.get("dark_image", 0) or 0)
    pedestrians = float(pct.get("pedestrians", 0) or 0)
    close = float(pct.get("close_in_image", 0) or 0)
    options = []
    if dark_pct >= 10:
        options.append({
            "id": "visibility", "title": "Explore clearer nighttime visibility",
            "observed": f"The camera recorded low overall brightness in {dark_pct:.0f}% of analyzed frames.",
            "change": "Preview improved image exposure and emphasize hard-to-see road users.",
            "why": "Seeing pedestrians, motorcycles and obstacles sooner can be important, but video exposure is not road illumination.",
            "validate": "Measure real lighting, camera exposure and retroreflectivity on site before recommending infrastructure.",
            "claim": "Illustrative image-exposure preview; NOT a simulation of installing streetlights.",
            "evidence_based": True
        })
    if pedestrians >= 5 and has_traffic:
        options.append({
            "id": "pedestrians", "title": "Review pedestrian–vehicle separation",
            "observed": f"People appeared in {pedestrians:.0f}% of frames and vehicles in {pct.get('vehicles', 0):.0f}%. Image-close pairs appeared in {close:.0f}% (not physical distance).",
            "change": "Highlight pedestrian detection positions and areas worth inspecting.",
            "why": "Helps reviewers find possible interaction locations in the real footage; it does not prove a collision risk.",
            "validate": "Verify detections, road use and pedestrian paths. A crosswalk is NOT automatically recommended.",
            "claim": "Visual attention overlay, not a prediction of reduced accidents.",
            "evidence_based": True
        })
    if has_traffic and float(avgs.get("vehicles", 0) or 0) >= 1:
        options.append({
            "id": "flow", "title": "Understand vehicle movement",
            "observed": f"Vehicles were detected in {pct.get('vehicles', 0):.0f}% of the {frames} sampled frames.",
            "change": "Draw observed movement trails over the same video to make route patterns easier to see.",
            "why": "Route patterns can identify locations to review, but image-plane tracks do not reveal exact speed or distance.",
            "validate": "Compare with manually checked trajectories and site geometry before engineering changes.",
            "claim": "Observed AI tracks only; missing or switched IDs can give incomplete trails.",
            "evidence_based": True
        })
    if not options:
        options.append({
            "id": "inspection", "title": "Inspect the actual road footage",
            "observed": f"Only {frames} frames have been analyzed; no specific physical change has sufficient evidence.",
            "change": "Show the actual image without a fabricated road modification.",
            "why": "The footage is not sufficient to justify a specific engineering change.",
            "validate": "Obtain longer, representative footage and verify detector accuracy.",
            "claim": "No engineering benefit can be calculated from the available evidence.",
            "evidence_based": False
        })
    # Concepts are always optional, never presented as measured video findings.
    options.append({
        "id": "markings", "title": "Concept · review reflective lane guidance",
        "observed": "Road marking quality and reflectivity have not been measured in this footage.",
        "change": "Show a lane-guidance concept only in 3D inspection view; real-image lane locations need calibration.",
        "why": "Reflective markings can aid guidance, but they cannot be located safely from a generic highway template.",
        "validate": "Survey existing lane boundaries and road category before drawing markings on the roadway.",
        "claim": "Unverified design concept, not a recommendation validated by this recording.",
        "evidence_based": False
    })
    return {"scenarios": options, "initial": next((x["id"] for x in options if x["evidence_based"]), "inspection")}


def candidate_site_review(events: list[dict], evidence: dict) -> dict | None:
    """A field-study recommendation grounded in repeated event timestamps.

    Not authorization for a signal. Two *distinct* time windows of repeated
    tracked image-point proximity and usable sampled-frame coverage are
    required before identifying a recurrent review location.
    """
    if len(events)<2:
        return None
    observed_frames=int(evidence.get("analyzed_frames",0) or 0)
    if observed_frames<12:
        return None
    ordered=sorted(events,key=lambda e:float(e.get("video_second",0)))
    windows=[]
    for event in ordered:
        try:
            stamp=float(event["video_second"])
            if int(event["frame_count"])<3:
                continue
        except (ValueError,KeyError,TypeError):
            continue
        if not windows or stamp-windows[-1]>2.0:
            windows.append(stamp)
    if len(windows)<2:
        return None
    stamp_text=", ".join(f"{t:.1f}s" for t in windows[:5])
    return {
        "id":"repeated_interaction_study",
        "title":"Review repeated pedestrian–vehicle interaction moments",
        "evidence":f"Sustained image-point proximity occurred in {len(windows)} separate time windows at approximately {stamp_text}. This is not measured physical clearance.",
        "reason":"Repeated co-location in the video view merits review of how pedestrians and vehicles use the available space. Tracking errors or perspective can produce misleading proximity.",
        "action":"Inspect the recorded moments and existing facilities. If on-site review confirms recurrent uncontrolled crossing demand, compare appropriate safe-access treatments, including a controlled pedestrian crossing only where engineering guidance permits it.",
        "verify":"Verify roadway classification, physical participant positions, pedestrian demand, permitted movements, crossing location, site dimensions and traffic speeds before any signal or layout design.",
        "priority":"Targeted field review",
        "expected_benefit":"No real-world change measured. The optional 3D model demonstrates control logic only.",
        "confidence":"Time-stamped provisional observations; requires field verification",
        "simulation_option":"signal_concept",
    }
