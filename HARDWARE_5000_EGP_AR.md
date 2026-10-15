# Smart Road: budget hardware starter (Egypt, October 2026)

**Goal:** a fixed outdoor camera + local PC, then measured flat-road calibration
and eventually a live safety dashboard. A 4 MP IP camera alone does **not**
measure absolute depth, vehicle-to-vehicle bumper gaps or physical collision risk.

## Shopping / budget reference (reconfirm stock and delivery at checkout)

| Item | Model | Displayed EGP |
| --- | --- | ---: |
| Camera | Hikvision DS-2CD1043G0-I (4mm) | 1900 |
| IEEE 802.3af power injector | TP-Link TL-POE150S | 1020 |
| Ethernet cable, 10 m | Ugreen Cat6 | 277 |
| Tape measure, 10 m | Total | 320 |
| **Displayed subtotal** | | **3517** |

Reserve **1483 EGP** for shipping, approved camera mounting, safe cable routing,
visible ground markers and contingencies. A safe elevated permanent installation
may cost more than this budget; do not install above active traffic yourself.
A laptop/PC with OpenCV, and an existing local router, are assumed.

**Retail links (prices change):**
- Camera: https://compu-station.com/shop/camera/camer-hikvision-out-door-4mp-ip-ds-2cd1043g0-i4mmc/
- Injector: https://shop.itegy.com.eg/product/tl-poe150s-poe-injector/
- Cable: https://www.jumia.com.eg/ar/ugreen-cat-6-uutp-lan-cable-10m-20164-black-134934491.html
- Tape: https://www.noon.com/egypt-ar/steel-measuring-tape-10m-25mm/Z51E0466B9E01647C30FBZ/p/

## Day 1: software, no hardware purchase

From project root on Windows:

    py -m venv .venv
    .venv\Scripts\activate
    pip install opencv-python numpy
    python local_camera_probe.py --file "C:\path\to\road.mp4" --seconds 10

This confirms video decode and prints JSON with frame size and receive rate.
It does **not** run YOLO or claim measured speed or collision risks.

## Day 2: physical camera setup, once hardware is available

1. Install the camera in an authorized safe schoolyard or supervised location,
   pointed at a fixed portion of road; never obstruct traffic or stand in
   moving lanes. Obtain permission and respect privacy requirements.
2. Connect **router LAN -> PoE injector LAN IN**, then **injector PoE OUT ->
   Hikvision camera** through the 10 m cable. Plug the injector's supplied
   power adapter into a safe indoor mains socket. Keep mains and the injector
   indoors and dry. The camera should not connect straight to ordinary USB.
3. Activate camera with its supported management interface, set a **new,
   strong password**, note its **private IPv4** address (e.g. 192.168.1.64),
   enable local RTSP and use H.264 for broad decoder compatibility.
4. Test video on the **same private LAN** before considering any internet
   access. Do **not** open RTSP port 554 to the public internet.
5. Run:

    python local_camera_probe.py --ip 192.168.1.64 --seconds 10

   The program prompts for the camera password, without printing it, and
   probes the main stream (channel 101). If the PC is slow, retry with
   "--substream" (channel 102). It reads only up to 80 frames and keeps no
   photos or recordings.

## Day 3: physical calibration and acceptance tests

1. Fix camera position, focal setting, image resolution and orientation.
   If the camera moves or zooms, repeat calibration.
2. From a **safe accessible flat ground patch** (for instance a yard,
   not a public road lane), mark and measure the four corners of a
   known rectangle (e.g. 3 m × 6 m). Record actual dimensions with the tape.
3. Match the 4 visible corners to their image coordinates in the
   Smart Road surveyed calibration UI, then measure a separate **fifth**
   checkpoint not used to fit the mapping.
4. Compare projected checkpoint coordinates with independently measured
   ground truth. Repeat at several positions; log absolute and relative
   errors. Reject calibration if the residual errors are unacceptable.
5. Only **ground-plane contact locations** can be mapped through this
   single-camera homography. Bounding-box bottom points are only rough
   substitutes for wheel contact, especially under occlusion. Camera-to-
   object depth and vehicle body clearances are not recovered.
6. Record test clips in good light and bad light; hand-verify tracking IDs,
   vehicle counts and reference distances against ground truth.

## Milestones / non-goals

- **M1 (implemented):** local video or private RTSP connection diagnosis
  using local_camera_probe.py; no camera secrets stored on GitHub.
- **M2 (next):** a separate, authenticated local bridge forwarding only
  selected, anonymized measurements (not RTSP credentials) to the
  Smart Road dashboard. The public Streamlit server must never try
  to access the user's 192.168.x.x camera directly.
- **M3:** reusable calibration saved per physical camera installation,
  independent checkpoint validation and per-measurement uncertainty.
- **M4:** streaming risk-review cards, with unknown metrics shown explicitly
  as **unmeasured** rather than unsafe; actual 3D geometry remains a
  calibrated/assumed visual model, not a scanned 3D road surface.
- **M5:** traffic-signal and crossing *what-if* simulation based on
  observed demand and declared assumptions; no live traffic actuation.

**Security:** never post RTSP URLs, camera passwords or student footage
to public GitHub issues. Do not expose RTSP to the WAN, and minimize
retention of imagery containing faces or plates. Use a private network
and permission for recording.
