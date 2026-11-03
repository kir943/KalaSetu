import os
import re
from typing import Any
import httpx

from backend.qa import NO_SOURCE_FALLBACK, SARVAM_CHAT_MODEL, SARVAM_CHAT_URL

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_TTS_MODEL = "bulbul:v3"
DEFAULT_SPEAKER = "shubh"

LANGUAGE_MAP: dict[str, dict[str, Any]] = {
    "hi-IN": {
        "name": "Hindi",
        "script": "Devanagari",
        "target_language_code": "hi-IN",
        "speaker": DEFAULT_SPEAKER,
        "model": SARVAM_TTS_MODEL,
        "translate": True,
    },
    "mr-IN": {
        "name": "Marathi",
        "script": "Devanagari",
        "target_language_code": "mr-IN",
        "speaker": DEFAULT_SPEAKER,
        "model": SARVAM_TTS_MODEL,
        "translate": True,
    },
    "en-IN": {
        "name": "English",
        "script": "Latin",
        "target_language_code": "en-IN",
        "speaker": DEFAULT_SPEAKER,
        "model": SARVAM_TTS_MODEL,
        "translate": False,
    },
}

ALLOWED_TTS_LANGUAGES = set(LANGUAGE_MAP.keys())
MAX_TTS_CHARS = 2500


def _prepare_text_for_speech(text: str) -> str:
    """
    Strip raw URLs and bracketed entry IDs from the citation footer so TTS
    reads natural prose rather than spelling out HTTP URLs character-by-character.
    """
    cleaned = text.strip()
    # Remove raw http/https URLs
    cleaned = re.sub(r"\s*\|\s*https?://\S+", "", cleaned)
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    # Remove bracketed archive IDs like [ID: src-blue-pottery-dsource-01]
    cleaned = re.sub(r"\s*\[ID:[^\]]+\]", "", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip()


def translate_text_for_tts(text: str, target_language_code: str) -> str:
    """
    Translate grounded answer text into Hindi (hi-IN) or Marathi (mr-IN) in Devanagari
    script using the backend's verified Sarvam-105B chat completion capability.
    Raises RuntimeError on failure and never silently falls back to English.
    """
    lang_cfg = LANGUAGE_MAP.get(target_language_code)
    if not lang_cfg or not lang_cfg["translate"]:
        return text

    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Backend SARVAM_API_KEY is not configured.")

    lang_name = lang_cfg["name"]
    system_prompt = (
        f"You are a faithful translator for the KalaSetu Indian craft archive.\n"
        f"Translate the user's grounded craft answer accurately into {lang_name} using {lang_cfg['script']} script.\n"
        f"STRICT RULES:\n"
        f"1. Preserve all craft facts, material names, and source attributions accurately.\n"
        f"2. Do NOT add outside information or commentary.\n"
        f"3. Output ONLY the {lang_name} translation in {lang_cfg['script']} script and nothing else."
    )

    headers = {
        "api-subscription-key": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": SARVAM_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": 0.0,
        "max_tokens": 500,
    }

    try:
        response = httpx.post(
            SARVAM_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Failed to connect to Sarvam translation service for {lang_name}: {exc.__class__.__name__}"
        ) from exc

    if response.status_code != 200:
        detail = response.text[:250] if response.text else f"HTTP {response.status_code}"
        raise RuntimeError(
            f"Sarvam translation error for {lang_name} ({response.status_code}): {detail}"
        )

    try:
        data = response.json()
        choices = data.get("choices") or []
        translated = choices[0].get("message", {}).get("content") if choices else None
    except (ValueError, IndexError, AttributeError) as exc:
        raise RuntimeError(f"Invalid translation payload for {lang_name}.") from exc

    if not translated or not str(translated).strip():
        raise RuntimeError(f"Sarvam returned an empty {lang_name} translation.")

    return str(translated).strip()


def synthesize_speech_with_bulbul(
    text: str,
    target_language_code: str = "hi-IN",
    speaker: str = DEFAULT_SPEAKER,
) -> dict[str, Any]:
    """
    Convert grounded answer text to speech using Sarvam Bulbul (bulbul:v3).
    When target_language_code is 'hi-IN' or 'mr-IN', translates the answer text
    into Hindi or Marathi first so Bulbul speaks in the selected language rather
    than reading English text aloud.
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

    lang_cfg = LANGUAGE_MAP[target_language_code]
    speech_ready_text = _prepare_text_for_speech(cleaned)

    if lang_cfg["translate"]:
        spoken_text = translate_text_for_tts(speech_ready_text, target_language_code)
        translated = True
    else:
        spoken_text = speech_ready_text
        translated = False

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": spoken_text[:MAX_TTS_CHARS],
        "target_language_code": lang_cfg["target_language_code"],
        "speaker": speaker or lang_cfg["speaker"],
        "model": lang_cfg["model"],
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
        "target_language_code": lang_cfg["target_language_code"],
        "speaker": speaker or lang_cfg["speaker"],
        "model": lang_cfg["model"],
        "spoken_text": spoken_text,
        "translated": translated,
    }
