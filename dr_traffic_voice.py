"""Optional Dr Traffic voice command processing.

This is a locally runnable Whisper adapter. It never assumes words prove a
traffic offence; the transcript is only a user note / evidence-capture request.
The heavy optional model is not a required dependency for the hosted UI.
"""
from __future__ import annotations

from pathlib import Path


def classify_voice_intent(text: str) -> str:
    words = " ".join((text or "").casefold().split())
    if any(s in words for s in ("تيك فوتو", "take photo", "التقط صورة", "خد صورة", "صورة", "photo")):
        return "capture_evidence_request"
    if any(s in words for s in ("إشارة", "اشارة", "traffic light", "red light", "signal")):
        return "traffic_signal_review_request"
    if any(s in words for s in ("نفايات", "زبالة", "رمي", "litter", "trash")):
        return "litter_review_request"
    if any(s in words for s in ("كتف الطريق", "shoulder", "حارة")):
        return "lane_review_request"
    return "general_voice_note"


def transcribe_voice(path: str | Path, *, language: str = "ar") -> dict:
    """Whisper voice note; optional dependency, runs when explicitly requested.

    Returns no assertion of synchronization with frame time or infraction.
    """
    file_path = Path(path)
    if not file_path.is_file() or file_path.suffix.lower() not in {".wav", ".mp3", ".m4a", ".ogg", ".mp4"}:
        raise ValueError("Choose a local audio file in WAV, MP3, M4A, OGG or MP4 format.")
    if file_path.stat().st_size > 35 * 1024 * 1024:
        raise ValueError("Voice note must be smaller than 35 MB.")
    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Whisper is not installed in this environment. For local use: "
            "pip install openai-whisper (FFmpeg required)."
        ) from exc
    model = whisper.load_model("base")
    output = model.transcribe(str(file_path), language=language, fp16=False)
    text = str(output.get("text", "")).strip()
    return {
        "transcript": text,
        "intent": classify_voice_intent(text),
        "command_requires_human_verification": True,
        "synchronized_to_video": False,
        "source": "optional_local_whisper",
    }
