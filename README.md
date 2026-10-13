# Smart Road AI

**Road intelligence from video, with evidence before conclusions.**

[Live Streamlit research demo](https://project-imqe2wriheusspmbnmgyxg.streamlit.app/) · Python 3.11 · Streamlit · Ultralytics YOLO · OpenCV

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
