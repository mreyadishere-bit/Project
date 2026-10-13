"""Measured object-detection QA from manually labeled video frames.

No ground truth => NO claimed precision, recall, F1, or detection accuracy.
Ground truth CSV columns: frame_number,class,x1,y1,x2,y2
Rows labeled class='none' declare known-empty frames. Only annotated frames
are scored; video frames without annotations are completely excluded.
"""
from __future__ import annotations
from collections import defaultdict
from io import StringIO
from pathlib import Path
import csv
import math


def _data(source):
    if isinstance(source,Path) or (isinstance(source,str) and "\n" not in source and "\r" not in source):
        with Path(source).open("r",encoding="utf-8-sig",newline="") as f:
            return list(csv.DictReader(f))
    if isinstance(source,bytes):
        source=source.decode("utf-8-sig")
    if hasattr(source,"read"):
        value=source.read()
        if isinstance(value,bytes):
            value=value.decode("utf-8-sig")
        source=value
    return list(csv.DictReader(StringIO(str(source))))


def _parse(rows,*,truth):
    by_frame=defaultdict(list)
    for n,row in enumerate(rows,2):
        try:
            frame=int(row["frame_number"])
            cls=str(row["class"]).strip().lower()
            if not cls:
                raise ValueError("Empty class")
            if frame<0:
                raise ValueError("Negative frame index")
            if cls=="none" and truth:
                by_frame.setdefault(frame,[])
                continue
            coords=[float(row[x]) for x in ("x1","y1","x2","y2")]
            if any(not math.isfinite(x) for x in coords):
                raise ValueError("Nonfinite bounding box")
            if not (coords[2]>coords[0] and coords[3]>coords[1]):
                raise ValueError("Invalid bounding box")
            by_frame[frame].append((cls,tuple(coords),
                                    float(row.get("confidence") or 1)))
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError(f"Invalid annotation or detection at CSV line {n}: {exc}") from exc
    return by_frame


def _iou(a,b):
    x1=max(a[0],b[0]);y1=max(a[1],b[1])
    x2=min(a[2],b[2]);y2=min(a[3],b[3])
    inter=max(0,x2-x1)*max(0,y2-y1)
    area_a=(a[2]-a[0])*(a[3]-a[1])
    area_b=(b[2]-b[0])*(b[3]-b[1])
    union=area_a+area_b-inter
    return inter/union if union else 0.


def _score(tp,fp,fn):
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    f1=(2*precision*recall/(precision+recall) if precision+recall else 0.0) if precision is not None and recall is not None else None
    return {
        "tp":tp, "fp":fp, "fn":fn,
        "precision":round(precision,4) if precision is not None else None,
        "recall":round(recall,4) if recall is not None else None,
        "f1":round(f1,4) if f1 is not None else None,
    }


def evaluate_detections(ground_truth, objects_file, *, iou_threshold=.50):
    if not .2<=iou_threshold<=.9:
        raise ValueError("IoU threshold must be between .20 and .90")
    labeled=_parse(_data(ground_truth),truth=True)
    if not labeled:
        raise ValueError("No annotated frames supplied; accuracy cannot be computed")
    # Read predictions incrementally; keep only deliberately labeled frames.
    predicted=defaultdict(list)
    with Path(objects_file).open(encoding="utf-8-sig",newline="") as source:
        reader=csv.DictReader(source)
        for r in reader:
            try:
                frame=int(r.get("frame_number",-1))
            except (ValueError,TypeError):
                continue
            if frame in labeled:
                predicted[frame].append(r)
    # Parse a single subset: avoids allocating full video predictions.
    parsed_pred=_parse([r for group in predicted.values() for r in group],truth=False)
    counts=defaultdict(lambda:[0,0,0])
    for frame,truths in labeled.items():
        by_class=defaultdict(list)
        for cls,box,conf in truths:
            by_class[cls].append(box)
        predictions=defaultdict(list)
        for cls,box,conf in parsed_pred.get(frame,[]):
            predictions[cls].append((box,conf))
        for cls in set(by_class)|set(predictions):
            expected=by_class.get(cls,[])
            guesses=sorted(predictions.get(cls,[]),key=lambda p:-p[1])
            matched=set()
            for box,confidence in guesses:
                eligible=[(j,_iou(box,gt)) for j,gt in enumerate(expected)
                          if j not in matched]
                if not eligible:
                    counts[cls][1]+=1
                    continue
                choice,score=max(eligible,key=lambda item:item[1])
                if score>=iou_threshold:
                    matched.add(choice);counts[cls][0]+=1
                else:
                    counts[cls][1]+=1
            counts[cls][2]+=len(expected)-len(matched)
    totals=[sum(item[i] for item in counts.values()) for i in range(3)]
    return {
        "evaluation_type":"Ground-truth object detection QA (NOT tracking accuracy)",
        "annotated_frames":len(labeled),
        "iou_threshold":iou_threshold,
        "overall":_score(*totals),
        "classes":{cls:_score(*values) for cls,values in sorted(counts.items())},
        "limitations":"Only explicitly annotated frames count. Unlabeled frames are excluded. "
                      "This measures box overlap and class, not vehicle uniqueness, "
                      "camera calibration, physical speed, tracking continuity, or safety prediction.",
    }
