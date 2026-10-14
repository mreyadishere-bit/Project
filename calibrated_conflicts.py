"""Ground-plane trajectory conflict *review candidates*, not predicted collisions.

Only available after independently supplied planar road calibration.
Constant-velocity surrogate calculations are not validated TTC/PET measurements.
Track identities, ground-contact inference and future motion can be wrong.
"""
from __future__ import annotations

from collections import defaultdict
from math import hypot
from statistics import median

VEHICLES={"car","truck","bus","motorcycle","bicycle"}


def _velocity_samples(track):
    samples=[]
    points=track.get("points") or []
    for prior,now in zip(points,points[1:]):
        t0,x0,y0=prior[:3]
        t,x,y=now[:3]
        dt=t-t0
        if not .10<=dt<=1.5:
            continue
        vx,vy=(x-x0)/dt,(y-y0)/dt
        if hypot(vx,vy)>47:
            continue  # inconsistent track, not evidence of superhuman braking
        samples.append((t,x,y,vx,vy))
    return samples


def ground_interaction_candidates(tracks_report, *, horizon_s=3.,
                                  closest_m=2.5, minimum_samples=2,
                                  max_events=24):
    """Return bounded, sustained pedestrian/vehicle approaches.

    Compare positions within 0.26s time bins; use a constant velocity
    extrapolation for at most 3s. This ignores acceleration and vehicle size.
    """
    if not .5<=horizon_s<=5 or not .5<=closest_m<=5:
        raise ValueError("Unsupported scenario proximity thresholds.")
    if minimum_samples<2 or max_events<1:
        raise ValueError("Multiple observations are required.")
    tracks=(tracks_report or {}).get("tracks",[])
    people=[t for t in tracks if t.get("class")=="person"][:40]
    vehicles=[t for t in tracks if t.get("class") in VEHICLES][:80]
    if not people or not vehicles:
        return []
    groups=defaultdict(lambda:{"p":[],"v":[]})
    for label,records in (("p",people),("v",vehicles)):
        for obj in records:
            for item in _velocity_samples(obj):
                timestamp=item[0]
                key=round(timestamp/.5)
                groups[key][label].append((obj["track_id"],obj["class"],item))
    episodes=defaultdict(list)
    for _,entries in sorted(groups.items()):
        for pid,_,(pt,px,py,pvx,pvy) in entries["p"]:
            for vid,vkind,(vt,vx,vy,vvx,vvy) in entries["v"]:
                if abs(pt-vt)>.30:
                    continue
                r=(px-vx,py-vy)
                vel=(pvx-vvx,pvy-vvy)
                speed2=vel[0]**2+vel[1]**2
                if speed2<.09:
                    continue
                projected=-(r[0]*vel[0]+r[1]*vel[1])/speed2
                if not 0<projected<=horizon_s:
                    continue
                closest=hypot(r[0]+vel[0]*projected,r[1]+vel[1]*projected)
                if closest>closest_m:
                    continue
                episodes[(str(pid),str(vid),vkind)].append(
                    ((pt+vt)/2,projected,closest,hypot(*r)))
    results=[]
    for (pid,vid,kind),record in episodes.items():
        record.sort()
        clusters=[]
        current=[]
        for row in record:
            if current and row[0]-current[-1][0]>1.5:
                clusters.append(current)
                current=[]
            current.append(row)
        if current:
            clusters.append(current)
        for data in clusters:
            distinct={round(v[0]/.5) for v in data}
            if len(distinct)<minimum_samples:
                continue
            results.append({
                "type":"constant_velocity_ground_approach_review",
                "video_second":round(median(p[0] for p in data),2),
                "person_track":pid,"vehicle_track":vid,"vehicle_class":kind,
                "supporting_time_bins":len(distinct),
                "model_time_to_closest_approach_s":round(min(p[1] for p in data),2),
                "model_closest_point_distance_m":round(min(p[2] for p in data),2),
                "interpretation":"Constant-velocity ground-point extrapolation only. This is not validated TTC, collision detection, PET or a certified near miss.",
                "check":"Independently validate planar calibration, participant ground contacts, tracking continuity, and actual right-of-way before drawing conclusions.",
            })
    results.sort(key=lambda a:(a["video_second"],-a["supporting_time_bins"]))
    return results[:max_events]
