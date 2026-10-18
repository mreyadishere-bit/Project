# Dr. Traffic — new primary project

The primary Streamlit route (\`app.py\`) now loads \`dr_traffic_app.py\`, not Smart
Road's former landing page. The previous project remains fully recoverable
on GitHub branch \`backup-smart-road-before-dr-traffic-2026-10-18\`. Old source
modules are temporarily retained on main until replacement and tests have
been verified. **Do not delete user footage or stored data blindly.**

## Source / provenance

Requested reference: https://www.youtube.com/watch?v=mYj4HtFFLug
The YouTube video could not be accessed as a complete playable video or
transcript within the assistant's environment. The **user-provided technical
outline** is the current implementation reference, not a claimed full
transcription of the source.

## What works now

- Premium mobile-responsive Streamlit upload and results workspace.
- YOLO26 video object detection on sampled frames (model downloads required).
- ByteTrack or BoT-SORT tracking via Ultralytics \`model.track\`.
- Image-line crossing candidate events with timestamps, track IDs,
  event cards and small annotated evidence stills.
- Explicitly *manual* optional red-signal time interval. The model does not
  infer the actual light phase or confirm illegal crossing.
- Original-video playback and downloadable structured JSON evidence.
- Local optional Whisper transcribe helper: audio upload and intent
  classification on systems with \`openai-whisper\` and FFmpeg installed.
  The Streamlit hosting requirements deliberately do not download Whisper
  models, and show a transparent unavailable status if not installed.
- Automated regression tests for crossing rules and speech intent mapping.

## Important unimplemented capabilities

- A separately trained Egyptian license-plate detector + Arabic OCR (not
  available from general pretrained YOLO classes).
- Vehicle paint color, make and model recognition.
- Road-shoulder/lane segmentation and validated wrong-way detection.
- Small-object trajectories and dedicated littering recognition.
- Automatic red/green light reading aligned to each vehicle's actual stop
  line. Manual red intervals are not a replacement for this.
- Qwen-VL scene interpretation and verification. Should be event-triggered
  and should never invent facts.
- Fully live low-latency camera/Jetson deployment.
- Violation precision/recall benchmarking against independently reviewed
  footage; no legal determination or police/database integrations.

## Local quick start

    python -m pip install -r requirements.txt
    streamlit run app.py

First inference downloads the chosen YOLO weights if not already cached.
An internet connection or a local weights cache is required.
For optional local voice:

    python -m pip install openai-whisper

Install FFmpeg separately. The UI never treats a voice command as a
legal finding.

## Safety / evidence integrity

- Do not upload recordings without the necessary permission.
- No plate recognition or vehicle ownership lookup is performed in V1.
- Uploaded recordings are stored temporarily in the Streamlit worker and
  can be removed when starting a new analysis; note that server persistence
  and retention must be assessed before production use.
- JSON counts are sampled frame observations, not unique traffic totals.
- A detection confidence is not a legally calibrated probability.
- The source's audio is not automatically synchronized with events.
- No speed, calibrated distance or true 3D reconstruction is claimed.
- Every event says **requires human review**, not "confirmed violation".

## Recommended next build

1. Collect permissioned annotated videos and measure detector/tracker quality.
2. Train a license-plate detector and evaluate Arabic OCR with uncertainty.
3. Introduce signal-state ROI and geometry validation across frames.
4. Add roadway segmentation and specific violation candidate rules.
5. Add small-object litter trajectory and Qwen optional review only on
   selected short clips.
6. Establish an authenticated local camera bridge and benchmark latency.
