# Smart Road AI VNext — implementation and verification

## What is implemented

This release is a working research prototype, not a certified road safety assessment.

- **Time-localized evidence**: safety_interactions.py scans actual tracking records
  and extracts sustained pedestrian/vehicle image-space proximity events with
  timestamps, IDs, support frames and uncertainty. They are NOT confirmed collisions.
- **Traffic microsimulation**: traffic_control_sim.py deterministically models
  approach cars, car following, stop lines, signal green/yellow/all-red, pedestrian
  WALK and clearance, queues and vehicle/pedestrian waiting. Identical seeded
  arrivals feed the unmanaged and signal-controlled comparison.
- **Actual 3D intervention**: traffic_control_view.py renders low-poly road
  geometry, vehicles with wheels/cabins, pedestrians, signals and a functioning
  crossing with an independent scenario clock. The left video stays real.
  Orbit/top viewing, timeline, playback and optional assumed flow/signal controls
  are integrated into the website.
- **Modeled metrics**: pedestrian waiting, vehicle travel time, maximum queue,
  stop time and throughput; never presented as measured crash reductions.
- **Measured detector evaluation**: detection_qa.py reports precision, recall and
  F1 only when labeled frame CSV evidence exists. Unlabeled frames are excluded.
- **PDF reporting**: road_report_pdf.py produces an evidence/limitations report
  with hypothetical simulation parameters/metrics when a scenario was generated.
- **Presentation**: the old yellow-circle demo is not the primary hosted result.
  Filename text is no longer actionable classification of road geometry.
- **Preservation**: the previous main branch is backed up as
  backup-before-road-safety-vnext-20261013.

## Continued improvements

- Evidence review now includes a **Watch supporting video at timestamp** action.
  It prefers the unchanged playable source recording, and distinctly labels
  annotated-video fallback whenever original playback is not available.
- Recurrent review proposals now require at least two independent temporal
  windows and sufficient frames. They can suggest studying an appropriate
  pedestrian-access treatment, but NEVER assert an unmeasured conflict.
- The working concept supports 1–3 assumed same-direction approach lanes.
  Car lane assignments, queues, and visual lane markings all update together.
- A visible 3D countdown/control-status panel shows changing traffic phases and
  how many cars are on screen versus pedestrians walking/waiting.
- Camera view is focused closer to the crossing and the zebra marking direction
  is physically consistent with pedestrians crossing across the carriageway.
- CI stress tests multiple seeds/flow settings and lane counts.
- Real Playwright/Chromium testing loads both an actual browser-decodable VP8
  source video and the right-hand WebGL scene, exercising WALK/STOP, pause and
  top-view. This validates browser mechanics but NOT accuracy against the
  uploaded road.

## 2026-10-14 — Camera-calibrated road and tracking

- The normal zero-settings analyzer remains intact. After processing,
  users can optionally enter four REAL image corners of a surveyed flat
  road patch, measured width and length, and their known/estimated camera FOV.
  Camera pose fitting and reprojection validate consistency, not absolute
  physical survey accuracy.
- Calibrated ground-plane positions and conservative vehicle speed samples
  are recomputed from the existing video tracking CSV, without running YOLO
  again. Results include uncertainty, bounded memory and reject motion
  discontinuities and unreasonable values.
- Optional automatic image-line/vanishing point hints help reviewers inspect
  perspective. They never claim verified lanes, road type, road width or
  metric 3D depth.
- The true-scale surveyed viewer uses the source road image as a planar
  texture, tracked vehicle world positions, real image camera pose, source,
  top and orbit views. WebGL itself reprojects all four surveyed corners,
  displays its reprojection error, and preserves a proper right-handed
  OpenCV-to-Three coordinate transformation.
- A working hypothetical crossing/signal can run ON the same surveyed road
  patch, with independent modeled timing, controls, vehicle queues and
  pedestrian movement. Agents are clipped to the measured road patch rather
  than stretching the 140 m traffic model into 25 m.
- Motion-gated global LAP data association helps maintain IDs without
  dropping raw YOLO detector boxes. No accuracy improvement is claimed
  without manually labeled ground truth.
- Reviewer-surveyed metrics appear in the PDF and JSON exports.
- CI tests analytical camera pose and reprojection, source WebGL scene,
  optional signal, motion regression, and long-video bounded samples.

NOT completed: Full monocular photogrammetry; automatic metric road geometry;
verified safe crossing engineering design; physically calibrated near-miss TTC;
fully benchmarked detector precision; full always-on, private, scalable
multi-camera pipeline; production map, weather, route and moderated reports.
An accurate road survey and camera intrinsics remain prerequisites for
physically meaningful km/h and sizes.

## Browser verification procedure

1. Upload and analyze video on the hosted site.
2. Find time-indexed items under Events worth reviewing. These are provisional.
3. Select Generate interactive 3D crossing & signal simulation.
4. Left: unchanged source footage. Right: genuine orbitable 3D concept.
5. Confirm traffic stops before the modeled crossing while people get WALK.
   Pedestrians clear; vehicles resume only in their green phase.
6. Expand optional concept settings. Change signal timing and demand.
7. Review before/after modeled pedestrian wait and vehicle delay/queue tradeoffs.
8. Export reproducible JSON and professional PDF.
9. Optionally use manually labeled CSV to calculate measured detection quality.
10. Verify visual accuracy and model behavior independently in a real browser.

## New independent calibration integrity check (2026-10-14)

The expert Surveyed road calibration workflow now accepts an **optional
independently measured fifth point** (both image pixels as percentages and
surveyed ground X/Y in metres). After fitting the original four coplanar
corners, it predicts the fifth point's ground position and reports discrepancy.

- A checkpoint reused from any fitted corner is rejected.
- A checkpoint beyond the surveyed rectangle is rejected.
- An independent point disagreeing by more than 1.5 metres fails validation.
- Without a fifth point, the UI explicitly labels metric readings provisional.
- The fitted-corner PnP reprojection RMSE is no longer misleadingly presented
  as independent evidence of true road-scale accuracy.
- This check is only local validation of one flat planar patch. It does not
  establish a complete 3D digital twin, camera ground truth or calibrated
  geometry outside the surveyed region.

Tests: `tests/test_road_calibration_validation.py`, including consistency,
inconsistency, invalid/out-of-patch and reused-corner cases.

## Oct 14 follow-up: calibrated 3D first, independent measurement checks and robust counterfactuals

- The main results now **prioritize the source-camera-aligned 3D road model**
  once independently surveyed planar dimensions and corner positions are
  available. The generic one-way crossing concept is clearly separated into
  an explicitly hypothetical section.
- An optional truly independent **fifth surveyed point** validates the
  original four-corner homography beyond its fit anchors. Reusing an anchor
  is rejected. Failed external checks reject the camera-plane validation.
- Without that fifth point, physical speed and scene geometry are labeled
  **provisional** rather than assumed accurate.
- With an independently checked camera plane, the system can screen
  repeated time-indexed **pedestrian/vehicle constant-velocity approach
  candidates** from measured-plane tracked ground points. These are not
  certified TTC/PET or confirmed near misses. Time, minimum predicted
  ground-point distance and supporting observations can be inspected and
  exported.
- The signalized crossing simulation now uses **five paired random demand
  trials** and presents the median changes and trial ranges for pedestrian
  waits, vehicle journey time, queues, and throughput. It directly explains
  modeled benefits and disadvantages; these are sensitivity checks, not
  real-world crash prevention statistics.
- PDF/JSON exports include whether surveyed road geometry had an independent
  checkpoint and relevant reviewed approach candidate timestamps.

This does **not** replace surveying or establish exact 3D scene geometry
outside the planar patch. A fully autonomous 3D reconstruction still needs
reliable depth/segmentation, camera intrinsics and road measurements.

## Explicitly NOT finished

The site is NOT a photogrammetric digital twin of arbitrary footage. A monocular
camera alone does not reveal hidden road geometry, true depth, exact lane width,
physical speed or accidents averted. The new microsimulation is an exploratory
two-lane model with assumed demand and physical dimensions.

Still required for full master-prompt completion:
- Calibrated/verified source-specific road and lane reconstruction
- Field-validated near-miss / TTC / PET models and intervention feasibility
- Robust human-labeled multi-camera CV benchmarking and detector improvements
- Production video workers / checkpoints / always-on authorized live analytics
- Full smart risk map, secure moderated citizen reports, weather and routing
- Security/privacy review, durable storage, accessibility and load testing
- End-to-end browser/video rendering tests across devices
- Licensed source/asset audits, especially detector license obligations

Treat the integrated pipeline as a tested research implementation, not a
road-authority-approved design or an AI accident predictor.
