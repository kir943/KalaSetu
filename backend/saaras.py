import os
from pathlib import Path
from typing import Any
import httpx

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STT_MODEL = "saaras:v3"

ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac", ".webm"}
ALLOWED_LANGUAGES = {"hi-IN", "mr-IN", "en-IN"}
MAX_AUDIO_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB


def validate_audio_upload(filename: str, file_bytes: bytes, language_code: str = "hi-IN") -> None:
    if not filename or not filename.strip():
        raise ValueError("Audio filename is missing.")

    ext = Path(filename.strip()).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_AUDIO_EXTENSIONS))
        raise ValueError(f"Unsupported audio format '{ext}'. Allowed formats: {allowed_str}")

    if not file_bytes or len(file_bytes) == 0:
        raise ValueError("Uploaded audio file is empty.")

    if len(file_bytes) > MAX_AUDIO_SIZE_BYTES:
        raise ValueError("Uploaded audio file exceeds maximum allowed size (15 MB).")

    if language_code not in ALLOWED_LANGUAGES:
        raise ValueError(f"Unsupported language_code '{language_code}'. Allowed: {', '.join(sorted(ALLOWED_LANGUAGES))}")


def format_segment_from_timestamps(timestamps: Any) -> tuple[str, bool]:
    """
    Derive source segment label from Saaras response timestamps if available.
    Never invent timestamps: if start_time_seconds / end_time_seconds are missing or empty,
    return a clearly labeled chunk-level source.
    """
    if isinstance(timestamps, dict):
        starts = timestamps.get("start_time_seconds")
        ends = timestamps.get("end_time_seconds")
        if isinstance(starts, list) and isinstance(ends, list) and len(starts) > 0 and len(ends) > 0:
            try:
                start_sec = float(starts[0])
                end_sec = float(ends[-1])
                return f"Segment 1 ({start_sec:.1f}s - {end_sec:.1f}s)", True
            except (TypeError, ValueError):
                pass
    return "Chunk 1 (Full uploaded audio clip — timestamps not returned by Saaras)", False


def transcribe_audio_with_saaras(
    file_bytes: bytes,
    filename: str,
    content_type: str = "audio/wav",
    language_code: str = "hi-IN",
) -> dict[str, Any]:
    """
    Send audio to Sarvam Saaras Speech-to-Text API and return transcript + source metadata.
    """
    validate_audio_upload(filename, file_bytes, language_code)

    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Backend SARVAM_API_KEY is not configured.")

    headers = {
        "api-subscription-key": api_key,
    }
    files = {
        "file": (filename, file_bytes, content_type or "audio/wav"),
    }
    data = {
        "model": SARVAM_STT_MODEL,
        "mode": "transcribe",
        "language_code": language_code,
        "with_timestamps": "true",
    }

    try:
        response = httpx.post(
            SARVAM_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Failed to reach Sarvam Saaras API: {exc.__class__.__name__}") from exc

    if response.status_code != 200:
        # Never expose API key; report upstream status and concise message
        detail = response.text[:250] if response.text else f"HTTP {response.status_code}"
        raise RuntimeError(f"Sarvam Saaras API error ({response.status_code}): {detail}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid JSON response received from Sarvam Saaras API.") from exc

    transcript = str(payload.get("transcript") or "").strip()
    timestamps = payload.get("timestamps")
    segment, has_exact_timestamps = format_segment_from_timestamps(timestamps)

    return {
        "request_id": payload.get("request_id"),
        "transcript": transcript,
        "language_code": payload.get("language_code") or language_code,
        "source_audio": filename,
        "segment": segment,
        "has_exact_timestamps": has_exact_timestamps,
    }
