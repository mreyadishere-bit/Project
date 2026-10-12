# Smart Road AI — Video Intelligence v2

Experimental road monitoring dashboard with **long-form video processing**, YOLO object detection and tracking, CSV streaming exports, and optional local webcam mode. Also includes a prototype citizen report map, weather and ESP32 sensor receiver in local mode. **Not a certified accident-detection or road-safety system.**

## Quick start (Windows, Python 3.11)

```powershell
git clone https://github.com/mreyadishere-bit/Project.git
cd Project
setup_windows.bat
run_windows.bat
```

Open <http://localhost:8501>. **Next time**, just run `run_windows.bat`: it checks GitHub for updates and updates Python packages before starting. If the app is already running, restart it for new code. Never force-pull over local changes; CSV and SQLite are excluded from Git.

## Cloud preview

The **repo is not itself a running website**. Deploy once through [Streamlit Community Cloud](https://share.streamlit.io/) using repository `mreyadishere-bit/Project`, branch `main`, entry point `app.py`, and environment variable `SMART_ROAD_HOSTED=1`. An online test deployment can analyze small/medium uploads but is limited by hosted RAM/CPU and storage; it cannot read the visitor's PC file paths or webcam with `cv2.VideoCapture(0)`. For hours of video, run the local app or provision a dedicated video server.

## What is actually measured

- YOLO object type/confidence and bounding boxes, ByteTrack IDs, image-plane motion direction (not km/h).
- Video can be longer than 60 seconds; file frames are sampled by configurable FPS. Wall-clock speed depends on hardware.
- Incremental `frames.csv`, `objects.csv` and optional annotated MP4, saved locally under ignored `outputs/`.
- Video analysis is experimental; no validated accident prediction, pothole detection, or true speed estimation yet.

## Notes

- Do **not** publish footage containing private/sensitive details without permission. There is no account authentication in the experimental cloud preview.
- Never commit weights, private videos, credentials, sensor readings or the local SQLite database.
- The optional ESP32 receiver requires `ROAD_DEMO_KEY` to be explicitly set. Keep it on a trusted LAN only.
- See [README_AR.md](README_AR.md) and [VIDEO_V2_GUIDE_AR.md](VIDEO_V2_GUIDE_AR.md) for the complete Arabic guides.
- Check the GitHub Actions `CI` workflow for syntax and integration-test results.

## License notice

Ultralytics software is distributed under AGPL-3.0 (or a separately obtained enterprise license). Check obligations before any public/commercial deployment. Original prototype code copyright remains with its contributors.
