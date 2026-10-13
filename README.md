# Smart Road AI

**Road intelligence from video, with evidence before conclusions.**

[Live Streamlit research demo](https://project-imqe2wriheusspmbnmgyxg.streamlit.app/) · Python 3.11 · Streamlit · Ultralytics YOLO · OpenCV

## V5.1 CPU performance and traffic detection QA (2026-10-13)

This update is based on visible issues in the same 18-second elevated
motorway video: many vehicles visible to a person but **zero tracked objects
in sampled frames**; actual CPU throughput around **3–4 FPS** despite a
higher requested analysis FPS; and an unrelated toy 2.5D road simulation
mistaken for a video reconstruction.

- Switched to a documented custom **BoT-SORT** tracker configuration tuned for
  stationary road cameras (`gmc_method: none`; track matching at lower
  confidence). Detector confidence defaults to `0.18` rather than `0.35`.
  **This may increase both recall and false positives**, and requires a labeled
  test before anyone can make accuracy claims.
- Processing presets now respect the CPU budget: Fast CPU (tiny model, 2
  sampled frames/second), Balanced (small model, 2), Deep (small, 5), and Max
  detail (medium model, 2, high-resolution). These are VIDEO sampling
  frequencies, not actual wall-clock inference throughput.
- Progress reports actual model inference ms, processed FPS, video FPS, sampled
  video-frame rate and fraction of sampled frames with no tracked objects.
  The interface warns if most frames lack detections despite visible traffic.
- **Optional detection ROI** focuses the pretrained model on selected road
  pixels to preserve detail on distant vehicles. Bounding boxes, reports,
  line-crossing counts, 3D positions and final video all use the original
  full-frame coordinates. A ROI cannot find cars outside the chosen region.
- **Optional OpenVINO acceleration**, based on open-source Intel OpenVINO.
  To enable locally, install `pip install openvino` and tick the checkbox.
  The first export may be slow. Cached future CPU inference can be faster;
  fallback to standard PyTorch is automatic. NOT installed by default on the
  free hosted server, to avoid unexpectedly increasing deployment memory.
- Removed the **unrelated toy 100 m highway simulation** from the primary
  video results page. The real video-derived 3D trajectory explorer remains
  behind a Generate button; without surveyed camera geometry it is still an
  approximate image-aligned visualization, NOT a faithful metric digital twin.

Useful open-source references: Ultralytics BoT-SORT configs
(<https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/trackers/botsort.yaml>),
Roboflow Supervision LineZone
(<https://supervision.roboflow.com/latest/detection/tools/line_zone/>),
OpenVINO integration (<https://docs.ultralytics.com/integrations/openvino>),
and optional SAHI slicing (<https://github.com/obss/sahi>) for particularly
small vehicles. SAHI full-video inference is **not enabled** here because
it would multiply CPU inference cost; a benchmark is needed before using it.

There are no guarantees of perfect detection, metric speed or 24/7 realtime
performance on a free shared CPU. Actual accuracy requires labeled examples
of this camera and measured ground truth. Existing synthetic CI tests validate
software behavior, not precision/recall on real traffic videos.

## Smart Road AI V5 — Grounded traffic analytics and camera-oriented 3D

This release addresses an important mistake in early versions: a count of two
visible cars in the final frame is **not** an accurate "total passed vehicles".

### What the upgraded analyzer measures

- **Current visible vehicles**: objects in one processed frame.
- **Track IDs recorded**: detector/tracker IDs, vulnerable to ID switches.
- **Vehicles passing a user-positioned horizontal line**: the number of distinct
  stable IDs observed crossing that line, with per-class, timestamp and
  image-direction evidence in `crossings.csv`.
- **Full video per-track measurements**: appearance duration, motion in
  pixels/s, and optional metric road distance, speed, heading and acceleration
  from sampled tracked footpoints if road-plane calibration is provided.
- **Road-plane calibration**: choose four **surveyed** corners of a real flat
  road rectangle and provide its real width/length and approximate camera
  horizontal FOV. Homography estimates metric positions; camera pose is
  estimated and reprojection-tested. These are still error-prone, not
  speed-enforcement measurements.
- **Precision profile**: Balanced uses a larger YOLO detector; Deep uses
  a heavier model with higher resolution/sampling, at additional CPU cost.
  BoT-SORT is used as the tracking preset.

### Interactive in-page video-driven 3D replay

After analysis finishes, click **Generate recommendations & 3D simulation**:

- All stable original track timestamps and observed 2D positions are exported
  for the browser 3D viewer, sampled evenly over the video timeline for bounded
  memory.
- Without road calibration, generic 3D agents overlay a **static real video
  reference frame**, keeping image locations aligned.
- With valid surveyed road calibration, a textured top-down road patch is
  projected onto a real-size ground plane with estimated original camera pose.
  Object footpoints use calibrated world coordinates and can be inspected
  from different camera angles. The camera pose also depends on an approximate
  horizontal FOV; an accurate match needs actual camera intrinsics.
- For **small annotated H264 videos only (up to 8 MB)**, playback and 3D
  observed/modified scenes share the same HTML5 video clock and scrubber.
  Larger videos use original timestamps without embedding the video again to
  avoid exploding browser memory.
- Editing proposed speeds, a crossing or an illustrative width displacement
  generates counterfactual **visuals**, not validated crash reduction forecasts.
  The system offers rule-based default interventions based on actual flags.

**These modes do not rebuild an exact 3D scene from a monocular fixed CCTV
camera.** Occluded objects, facades, body shape, mass, road elevations and
true hidden geometry remain unknown. The textured road patch is a photo
warped to an assumed flat surveyed surface, not a full photogrammetric mesh.
For a precision digital twin, obtain multi-view calibrated imagery / LiDAR
and a surveyed road geometry model, and validate with ground-truth traffic
observations. Free hosted Streamlit CPU cannot replace a dedicated GPU
inference/simulation backend for long high-res video.

**Verification:** Synthetic-video integrations, line-count debouncing, 3D
scene payload, surveyed perspective re-projection, Node module parse and
full Streamlit UI regression tests run in GitHub Actions. This is not a
measured accuracy benchmark on real labeled traffic footage. To claim
high accuracy, annotate a representative evaluation sample and report
precision/recall, counting error, ID switches and metric speed error.

## Smart Road AI v4 — video evidence & scenario lab

The hosted [Smart Road AI app](https://project-imqe2wriheusspmbnmgyxg.streamlit.app/) now defaults to **Upload video** (recorded footage) so repeatable analysis can be compared. Set `Create final playable video (H.264)` on before starting.

After the job finishes, the **same Workspace page** displays:

1. Plain-language executive summary, detector observations and an explicitly provisional review-priority index.
2. Embedded H.264 annotated video using frames **sampled across the source duration**, not every raw source frame; audio is not preserved.
3. Full-session class statistics, object contact-point activity heatmap, frame count trends and time-stamped observations.
4. Explainable rule-based recommendations, including the evidence that triggered each recommendation and what needs real-world verification.
5. Side-by-side animated **2.5D before/after traffic simulation** with adjustable assumed vehicle speeds, car volume, pedestrian arrivals and crossing interventions. The simulation is a `toy scenario`, not a calibrated prediction or reconstruction.
6. JSON summary plus complete CSV observations, tracking data and event log.

**Performance:** On shared free cloud CPU, analysis cannot promise realtime speed or consistent results across long uploads. Lower `Analysis profile` FPS for a quick scan or use a local/GPU worker for hours of deep analysis. A finished H.264 video export requires extra encoding time and temporary disk storage.

**Source and study limitations:** YOLO identifies only model-supported classes; potholes, water, road defects and verified crashes/near misses require additional trained models and measurement methods. Heatmap indicates where image detections occurred, not dangerous places. Approximate m/pixel speed has uncorrected perspective and should not be used for speed enforcement. A 2.5D illustrative scenario cannot establish real-world effectiveness; engineering review and collected before/after data are still required.

## What works today

- Long video files without a 60-second analysis cap in the local version (processing time/storage still depend on hardware).
- Recorded-video analysis on the hosted Streamlit demo, subject to server upload, memory and runtime limits.
- **YouTube Live (beta):** choose `YouTube Live (beta)` in Workspace and paste a specific public `https://www.youtube.com/live/VIDEO_ID` or `https://www.youtube.com/watch?v=VIDEO_ID` URL. The worker validates and resolves the authorized public live stream with `yt-dlp`, then attempts continuous latest-frame tracking in OpenCV. Only a small number of shared live workers are supported. It may fail due to YouTube restrictions, bot checks, region restrictions or limited Streamlit CPU resources. No scraping of private, protected, or DRM-protected streams.
- **Results discoverability:** the Workspace now shows cumulative sampled-frame counts, traffic timeline and the strongest detected frame when the final frame contains no objects. Open Intelligence for detailed tracks and Events & reports for CSV/JSON downloads.
- Vehicle/pedestrian detection, ByteTrack IDs, image-plane trajectories and processed frame rates.
- Frame-by-frame observations: counts by class, brightness, object bounding-box occupancy.
- Experimental scene flags: visually close pedestrian/vehicle detections, dark frames and crowded images.
- Image motion in pixels/second and **optional, approximate** km/h values only when a user supplies a metres-per-pixel scale.
- Events timeline; CSV exports for frames, objects and observations; JSON summary; optional annotated MP4.
- Premium responsive dashboard, designed for desktop and mobile with accessible native Streamlit controls.

## Explicit limitations

- This is **not** a validated accident predictor, near-miss detector, roadway speed camera, or safety-critical alert system.
- A single pixels-to-metres scale does **not** resolve camera perspective. Real speeds require surveyed geometry or homography calibration and validation.
- Apparent image overlap or proximity does not prove physical proximity. Camera depth, occlusion and movement are not solved.
- A dark video frame is not a photometric measurement of poor roadway lighting.
- Potholes, cracks, puddles and road damage require dedicated datasets/models and independent evaluation; **the current pretrained detector does not find them**.
- The public hosted app has no account-level access control. **Never upload sensitive/identifiable footage.**


## Free actual live traffic cameras (no YouTube)

Hosted demo: open **Workspace → Free Live Traffic Cameras**. Pick one of the
agency-operated Caltrans HLS feeds, click **Check first video frame**, and wait
for a real decoded image. Then click **Start analyzing**. Results refresh in the
workspace as frames arrive. No YouTube cookies, developer API tokens, or paid
camera service is required.

**Verified in GitHub Actions (2026-10-13):**

| Source | Provider | Live playlist status | Decoded frame |
| --- | --- | --- | --- |
| Sacramento — I-5 Pocket Rd | California DOT (Caltrans) | HTTP 200, HLS | Yes (JPEG produced by FFmpeg) |
| Southern California — D7 CCTV-101 | California DOT (Caltrans) | HTTP 200, HLS | Yes (JPEG produced by FFmpeg) |

This is an *availability spot-check*, not a guarantee the same network route
works from Streamlit Community Cloud or that a broadcast stays online. The
built-in **Check first video frame** button verifies the connection from the
actual app server before GPU/CPU model loading. Caltrans cameras are free to
view and accessible through the [official live camera directory](https://cwwp2.dot.ca.gov/vm/streamlist.htm);
the [agency conditions of use](https://dot.ca.gov/conditions-of-use) apply.
Only counters, analysis metadata and temporary previews are retained; do not
archive or republish agency camera footage without confirming permission.
Seattle DOT streams were not used as ready-to-run defaults because they timed
out during the test.

### If the camera is not reachable

1. Use **Check first video frame** to distinguish network/decoder failure
   from YOLO errors. Select the other official camera if the first fails.
2. Use a permitted recorded video in **Upload video** for consistent,
   repeatable testing regardless of external live availability.
3. Live camera processing on shared free CPU may skip frames and fall behind;
   a dedicated inference worker is needed for predictable 24/7 performance.

## Local quick start

Windows: run `setup_windows.bat` once, then `run_windows.bat`.

Cross-platform Python 3.11:

```bash
python -m venv .venv
# Activate your virtual environment, then:
python -m pip install -r requirements.txt
streamlit run app.py
```

Hosted mode: set `SMART_ROAD_HOSTED=1` in the deployment environment (or Streamlit secrets), point the deployment to `app.py`, and install `requirements.txt`.

## Next technical milestones

1. Geometric camera calibration (homography, region of interest, world-plane distance).
2. Road-specific defect detector trained on properly licensed and labeled imagery, with precision/recall measured.
3. Multi-object trajectory analytics with uncertainty and occlusion modeling; validated near-conflict metrics only after calibration.
4. Dynamic safety event review, clips and human confirmation workflow.
5. Dedicated background GPU/CPU worker with job queue, streaming storage, privacy controls and resumable long-video uploads.
6. Camera feeds via browser WebRTC or authorized RTSP ingress, with a stable production deployment.

All changes are tested with [GitHub Actions](https://github.com/mreyadishere-bit/Project/actions). The smoke tests use synthetic footage and mocked model predictions; a field validation set is still needed before real-world safety claims.

_Research prototype — not intended for live traffic control or enforcement._


## Live streaming realities

- An embedded YouTube player and AI frame reader have **different buffers and may be several seconds behind each other**. The app does **not** analyze browser-visible pixels and does **not** guarantee synchronization, uninterrupted capture, or full source FPS.
- Streamlit Community Cloud CPU cannot guarantee real-time analysis, 24/7 capture, or access to every public YouTube source. Some YouTube livestreams cannot be extracted from that hosting environment at all.
- To achieve sustained near-live, multiple cameras, low latency and reliable resumes, deploy a dedicated inference worker with monitored GPU capacity, authorized feeds (RTSP/HLS), a queue and retention/privacy policies.
