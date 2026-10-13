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
