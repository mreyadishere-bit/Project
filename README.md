# Smart Road AI

**Road intelligence from video, with evidence before conclusions.**

[Live Streamlit research demo](https://project-imqe2wriheusspmbnmgyxg.streamlit.app/) · Python 3.11 · Streamlit · Ultralytics YOLO · OpenCV

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
