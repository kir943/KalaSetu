import os
from typing import Any
import httpx

from backend.qa import NO_SOURCE_FALLBACK

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_TTS_MODEL = "bulbul:v3"
DEFAULT_SPEAKER = "shubh"
ALLOWED_TTS_LANGUAGES = {"hi-IN", "mr-IN", "en-IN"}
MAX_TTS_CHARS = 2500


def synthesize_speech_with_bulbul(
    text: str,
    target_language_code: str = "hi-IN",
    speaker: str = DEFAULT_SPEAKER,
) -> dict[str, Any]:
    """
    Convert grounded answer text to speech using Sarvam Bulbul (bulbul:v3).
    Refuses to synthesize the exact no-source fallback ('Mere paas iska source nahi hai.').
    """
    if not text or not text.strip():
        raise ValueError("Text for speech synthesis must not be empty.")

    cleaned = text.strip()
    if cleaned.lower() == NO_SOURCE_FALLBACK.lower():
        raise ValueError(
            f"Refusing to synthesize speech for the no-source fallback: '{NO_SOURCE_FALLBACK}'"
        )

    if target_language_code not in ALLOWED_TTS_LANGUAGES:
        raise ValueError(
            f"Unsupported target_language_code '{target_language_code}'. Allowed: {', '.join(sorted(ALLOWED_TTS_LANGUAGES))}"
        )

    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Backend SARVAM_API_KEY is not configured.")

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": cleaned[:MAX_TTS_CHARS],
        "target_language_code": target_language_code,
        "speaker": speaker or DEFAULT_SPEAKER,
        "model": SARVAM_TTS_MODEL,
    }

    try:
        response = httpx.post(
            SARVAM_TTS_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Failed to reach Sarvam Bulbul TTS API: {exc.__class__.__name__}") from exc

    if response.status_code != 200:
        detail = response.text[:250] if response.text else f"HTTP {response.status_code}"
        raise RuntimeError(f"Sarvam Bulbul TTS API error ({response.status_code}): {detail}")

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Invalid JSON response from Sarvam Bulbul TTS API.") from exc

    audios = data.get("audios")
    if not isinstance(audios, list) or not audios or not audios[0]:
        raise RuntimeError("Sarvam Bulbul TTS API returned no audio payload.")

    return {
        "request_id": data.get("request_id"),
        "audio_base64": audios[0],
        "mime_type": "audio/wav",
        "target_language_code": target_language_code,
        "speaker": speaker or DEFAULT_SPEAKER,
        "model": SARVAM_TTS_MODEL,
    }
