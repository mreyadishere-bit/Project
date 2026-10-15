"""Local-only camera connection test for Smart Road's low-cost hardware kit.

Runs on the PC on the same private LAN as the IP camera, never on the public
Streamlit server. It DOES NOT estimate physical speed or distance.
No RTSP URL, username or password is included in the JSON output.
"""
from __future__ import annotations

import argparse
import getpass
import ipaddress
import json
import os
from pathlib import Path
import time
from urllib.parse import quote


def private_camera_ip(value: str) -> str:
    """Allow only RFC1918 IPv4 addresses. Never probe public WAN endpoints."""
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Enter a private IPv4 address shown by your router.") from exc
    lan = (
        ipaddress.IPv4Network("10.0.0.0/8"),
        ipaddress.IPv4Network("172.16.0.0/12"),
        ipaddress.IPv4Network("192.168.0.0/16"),
    )
    if not any(address in block for block in lan):
        raise ValueError("For safety, only private local-network camera addresses are accepted.")
    return str(address)


def hikvision_rtsp(ip: str, username: str, password: str, *, substream=False) -> str:
    """Construct an authenticated RTSP URL; callers must never print it."""
    ip = private_camera_ip(ip)
    if not username or not password:
        raise ValueError("The camera username and password are required.")
    channel = "102" if substream else "101"
    return (
        f"rtsp://{quote(username, safe='')}:{quote(password, safe='')}"
        f"@{ip}:554/Streaming/Channels/{channel}"
    )


def probe_capture(capture, *, seconds: float = 10.0, max_frames: int = 80) -> dict:
    """Return bounded stream diagnostics without retaining or uploading images."""
    if not capture.isOpened():
        raise RuntimeError("Cannot open source. Check LAN, RTSP, credentials and video format.")
    import cv2

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    start = time.monotonic()
    observed = 0
    width = height = 0
    failures = 0
    while observed < max_frames and time.monotonic() - start < seconds:
        ok, frame = capture.read()
        if not ok or frame is None:
            failures += 1
            if failures >= 2:
                break
            continue
        failures = 0
        height, width = frame.shape[:2]
        observed += 1
    elapsed = max(time.monotonic() - start, 0.0001)
    if observed == 0:
        raise RuntimeError("Connected, but no decodable video frames arrived.")
    return {
        "status": "video_received",
        "frames_received": observed,
        "width": width,
        "height": height,
        "reported_source_fps": round(fps, 2) if 0 < fps < 240 else None,
        "frames_read_per_wall_second": round(observed / elapsed, 2),
        "elapsed_seconds": round(elapsed, 2),
        "note": "Connection test only. No AI inference, calibration, metric speed or collision prediction.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Test a LOCAL IP camera or recorded video.")
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--ip", help="Private camera IPv4 address, such as 192.168.1.64")
    sources.add_argument("--file", help="Local test video path; no camera required")
    parser.add_argument("--substream", action="store_true", help="Use lighter camera channel 102")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--frames", type=int, default=80)
    args = parser.parse_args(argv)
    if not 1 <= args.seconds <= 30 or not 1 <= args.frames <= 300:
        parser.error("Use 1–30 seconds and 1–300 frames.")

    # Silence OpenCV's own logging before importing its FFmpeg backend.
    os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
    import cv2

    if args.ip:
        try:
            ip = private_camera_ip(args.ip)
        except ValueError as exc:
            parser.error(str(exc))
        username = os.getenv("SMART_ROAD_CAMERA_USER") or "admin"
        password = os.getenv("SMART_ROAD_CAMERA_PASSWORD") or getpass.getpass("Camera password: ")
        address = hikvision_rtsp(ip, username, password, substream=args.substream)
        try:
            capture = cv2.VideoCapture(
                address, cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000,
                 cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000],
            )
        except (cv2.error, OSError):
            raise SystemExit("Could not connect to the private camera. No credentials were printed.")
        source = "private_lan_rtsp"
    else:
        path = Path(args.file).expanduser()
        if not path.is_file() or path.suffix.lower() not in {".mp4", ".avi", ".mov", ".mkv", ".m4v"}:
            parser.error("Choose an existing local video file (MP4, AVI, MOV, MKV or M4V).")
        capture = cv2.VideoCapture(str(path))
        source = "local_recording"
    try:
        try:
            result = probe_capture(capture, seconds=args.seconds, max_frames=args.frames)
        except (RuntimeError, OSError, cv2.error):
            raise SystemExit("Source not ready: check camera network, credentials and video encoding.")
    finally:
        capture.release()
    result["source_type"] = source
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
