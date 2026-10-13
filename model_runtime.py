"""Optional, zero-license-fee OpenVINO optimization for Intel-class CPUs.

Opt-in only: export is slow on the FIRST run, and an OpenVINO installation
must already be available in the Python environment. No silent downloads,
no model accuracy claims, and a clear fallback to PyTorch on failure.
"""
from __future__ import annotations

from pathlib import Path
import importlib.util
import threading

_LOCK=threading.Lock()


def load_detector(model_name, image_size, *, use_openvino=False):
    from ultralytics import YOLO
    model=YOLO(model_name)
    if not use_openvino:
        return model,"PyTorch"
    if importlib.util.find_spec("openvino") is None:
        return model,"PyTorch (OpenVINO not installed)"
    with _LOCK:
        try:
            exported=Path(model_name).with_suffix("")
            candidate=exported.parent / (exported.name + "_openvino_model")
            if candidate.is_dir() and (candidate/"model.xml").exists():
                return YOLO(str(candidate)),"OpenVINO (cached)"
            output=model.export(format="openvino",imgsz=image_size,dynamic=False,half=False)
            directory=Path(output)
            if not directory.exists():
                return model,"PyTorch (OpenVINO export returned no file)"
            return YOLO(str(directory)),"OpenVINO (exported)"
        except (OSError,ValueError,RuntimeError,ImportError) as exc:
            return model,f"PyTorch (OpenVINO unavailable: {type(exc).__name__})"
