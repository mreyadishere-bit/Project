"""Readable multi-page PDF road review report with explicit evidential limits.

No dangerous invented roadway design requirements, calibrated speeds,
collision predictions or accident-reduction claims.
"""
from __future__ import annotations

from html import escape
from io import BytesIO
from datetime import datetime, timezone

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
)

NAVY=HexColor("#182C49")
BLUE=HexColor("#2774C6")
GREY=HexColor("#6E8097")
BORDER=HexColor("#DFE7F0")

def _p(value,style):
    return Paragraph(escape(str(value)).replace("\n","<br/>"),style)

def build_road_pdf(snapshot,report,events,simulation=None,surveyed=None):
    buffer=BytesIO()
    document=SimpleDocTemplate(buffer,pagesize=A4,
            leftMargin=18*mm,rightMargin=18*mm,
            topMargin=20*mm,bottomMargin=19*mm,
            title="Smart Road AI — Evidence-based road review",
            author="Smart Road AI")
    base=getSampleStyleSheet()
    styles={
        "title":ParagraphStyle("TitleRoad",parent=base["Title"],fontName="Helvetica-Bold",fontSize=22,
                               leading=26,textColor=NAVY,spaceAfter=6),
        "subtitle":ParagraphStyle("SubtitleRoad",parent=base["Normal"],fontSize=10,
                                  leading=15,textColor=GREY,spaceAfter=13),
        "h":ParagraphStyle("HeadingRoad",parent=base["Heading2"],fontName="Helvetica-Bold",
                           fontSize=12.5,leading=16,textColor=NAVY,spaceBefore=15,spaceAfter=8),
        "body":ParagraphStyle("BodyRoad",parent=base["Normal"],fontSize=9.5,leading=14.5,
                              textColor=NAVY,spaceAfter=7),
        "small":ParagraphStyle("SmallRoad",parent=base["Normal"],fontSize=8,leading=12,
                               textColor=GREY,spaceAfter=7),
        "table":ParagraphStyle("TableRoad",parent=base["Normal"],fontSize=8.5,leading=12,
                               textColor=NAVY),
        "value":ParagraphStyle("ValueRoad",parent=base["Normal"],fontSize=14,leading=20,
                               textColor=BLUE,fontName="Helvetica-Bold"),
    }
    story=[]
    story.append(_p("SMART ROAD AI  /  ROAD REVIEW",styles["small"]))
    story.append(_p("Understand the road. Verify the evidence.",styles["title"]))
    story.append(_p("Computer vision observations and engineering-review concepts — not a certified road safety assessment.",styles["subtitle"]))
    story.append(_p("Analysis overview",styles["h"]))
    labels=[
        ("Recording",snapshot.get("label","Uploaded road video")),
        ("Source duration",f"{float(snapshot.get('duration_seconds') or 0):.1f} s"),
        ("Analyzed frames",int(snapshot.get("analyzed_frames") or 0)),
        ("Detected frames",int(snapshot.get("detected_frames") or 0)),
        ("Context",report.get("context",{}).get("label","Not established")),
    ]
    table=Table([[_p(k,styles["table"]),_p(v,styles["table"])] for k,v in labels],colWidths=[46*mm,120*mm],hAlign="LEFT")
    table.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LINEBELOW",(0,0),(-1,-2),.4,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    story.append(table)
    story.append(_p("What the camera observed",styles["h"]))
    story.append(_p(report.get("summary","No scene summary available"),styles["body"]))
    story.append(_p(report.get("limitations","Single-camera footage cannot establish the full road geometry."),styles["small"]))
    story.append(_p("Time-localized review candidates",styles["h"]))
    if not events:
        story.append(_p("No sustained image-space pedestrian–vehicle interaction could be established from tracked frames. This does not confirm that the road is safe.",styles["body"]))
    for n,event in enumerate(events[:12],1):
        content=[
            _p(f"{n}. {event.get('title','Interaction to inspect')} · {float(event.get('video_second',0)):.1f} s",styles["body"]),
            _p(f"Sampled interval: {event.get('start_second',0)}–{event.get('end_second',0)} s; "+
               f"supporting frames: {event.get('frame_count',0)}. "+
               event.get("explanation","Review before acting."),styles["small"])
        ]
        story.append(KeepTogether(content))
    story.append(_p("Engineering review recommendations",styles["h"]))
    for index,item in enumerate(report.get("recommendations",[])[:7],1):
        content=[
            _p(f"{index}. {item.get('title','Inspect site')}",styles["body"]),
            _p("Evidence: "+item.get("evidence","Unavailable"),styles["small"]),
            _p("Next step: "+item.get("action","Verify on site"),styles["body"]),
            _p("Verification: "+item.get("verify","Required"),styles["small"])
        ]
        story.append(KeepTogether(content))
    story.append(_p("Illustrative 3D traffic-control scenario",styles["h"]))
    if simulation:
        before=simulation.get("baseline",{}).get("metrics",{})
        after=simulation.get("managed",{}).get("metrics",{})
        rows=[[_p("Modeled metric",styles["table"]),_p("Unmanaged",styles["table"]),_p("Signal concept",styles["table"])]]
        for key,label in [
            ("mean_pedestrian_wait_s","Mean pedestrian wait (s)"),
            ("mean_vehicle_travel_s","Mean vehicle travel (s)"),
            ("max_waiting_vehicles","Maximum waiting vehicles"),
            ("vehicles_completed","Vehicles completed"),
            ("pedestrians_completed","Pedestrians completed")
        ]:
            rows.append([_p(label,styles["table"]),
                         _p(str(before.get(key,"N/A")),styles["table"]),
                         _p(str(after.get(key,"N/A")),styles["table"])])
        t=Table(rows,colWidths=[84*mm,40*mm,42*mm],repeatRows=1,hAlign="LEFT")
        t.setStyle(TableStyle([
            ("GRID",(0,0),(-1,-1),.3,BORDER),
            ("BACKGROUND",(0,0),(-1,0),HexColor("#ECF3FC")),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
            ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ]))
        story.append(t)
        story.append(Spacer(1,8))
        story.append(_p(simulation.get("methodology","Hypothetical simulation only."),styles["small"]))
    else:
        story.append(_p("No intervention simulation was run for this report. No safety benefit can be inferred.",styles["body"]))
    if surveyed:
        cal=surveyed.get("calibration",{})
        measurement=surveyed.get("tracks_report",{})
        story.append(_p("User-surveyed metric road patch",styles["h"]))
        story.append(_p(
            f"Four planar reference corners provided by reviewer. "
            f"Measured patch: {cal.get('width_m','?')} m wide × "
            f"{cal.get('length_m','?')} m long. "
            f"Camera pose fit RMSE: {surveyed.get('reprojection_error_px','?')} image pixels.",
            styles["body"]))
        speed=measurement.get("median_track_speed_kmh")
        story.append(_p(
            f"Tracked objects with enough valid surveyed-plane samples: "
            f"{measurement.get('accepted_track_count',0)}. "
            f"Median of the individual track speed estimates: "
            f"{str(speed)+' km/h' if speed is not None else 'not reliably available'}.",
            styles["body"]))
        story.append(_p(
            "These speeds rely on user-entered surveyed geometry and image "
            "footpoint assumptions. They are not radar measurements, "
            "certified speed enforcement evidence or measurements outside "
            "the surveyed flat patch. A low reprojection error alone "
            "does not validate the physical survey or object detections.",
            styles["small"]))
    story.append(_p("Next steps and scientific limits",styles["h"]))
    story.append(_p("Manually verify the relevant video moments, classify the roadway, "
                    "survey crossing demand and lane geometry, and obtain real-world "
                    "traffic speed and signal data before implementing physical changes. "
                    "Reported image-space proximity does not establish a collision, "
                    "physical separation, or a near miss.",styles["body"]))

    def page_decoration(canvas, doc):
        canvas.saveState()
        w,h=A4
        canvas.setStrokeColor(BORDER);canvas.setLineWidth(.7)
        canvas.line(18*mm,14*mm,w-18*mm,14*mm)
        canvas.setFillColor(GREY);canvas.setFont("Helvetica",8)
        canvas.drawString(18*mm,10*mm,"SMART ROAD AI  ·  RESEARCH REVIEW / NOT A ROAD DESIGN CERTIFICATION")
        canvas.drawRightString(w-18*mm,10*mm,f"Page {doc.page}")
        canvas.restoreState()
    document.build(story,onFirstPage=page_decoration,onLaterPages=page_decoration)
    return buffer.getvalue()
