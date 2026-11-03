from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.qa import NO_SOURCE_FALLBACK

client = TestClient(app)


def _make_chat_response(translated_text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "id": "chatcmpl-trans-001",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": translated_text},
                "finish_reason": "stop",
            }
        ],
    }
    return resp


def _make_bulbul_response(audio_b64: str = "UklGRvAZAwBXQVZFZm10IBAAAAABAA==") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "request_id": "tts-req-001",
        "audios": [audio_b64],
    }
    return resp


def test_tts_hindi_selection_translates_english_answer_before_bulbul():
    hindi_translation = (
        "जयपुर की ब्लू पॉटरी में प्राकृतिक मिट्टी का उपयोग नहीं किया जाता है। इसका आटा क्वार्ट्ज पत्थर के पाउडर, "
        "कांच के पाउडर, मुल्तानी मिट्टी और कतीरा गोंद से तैयार किया जाता है।"
    )
    mock_chat_resp = _make_chat_response(hindi_translation)
    mock_bulbul_resp = _make_bulbul_response()

    with patch("backend.tts.httpx.post", side_effect=[mock_chat_resp, mock_bulbul_resp]) as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": (
                    "Jaipur Blue Pottery does not use natural clay. Its dough is prepared from "
                    "powdered quartz stone, powdered glass, Multani Mitti, and Katira Gond.\n\n"
                    "Source: Blue Pottery of Jaipur — D'source | https://www.dsource.in/resource [ID: src-blue-pottery-dsource-01]"
                ),
                "target_language_code": "hi-IN",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == "UklGRvAZAwBXQVZFZm10IBAAAAABAA=="
        assert data["mime_type"] == "audio/wav"
        assert data["target_language_code"] == "hi-IN"
        assert data["model"] == "bulbul:v3"
        assert data["speaker"] == "shubh"
        assert data["translated"] is True
        assert data["spoken_text"] == hindi_translation
        assert "sk_" not in str(data)

        # Call 1: Translation request to Sarvam-105B
        assert mock_post.call_count == 2
        trans_args, trans_kwargs = mock_post.call_args_list[0]
        assert trans_args[0] == "https://api.sarvam.ai/v1/chat/completions"
        assert "Hindi" in trans_kwargs["json"]["messages"][0]["content"]
        # Raw URL and bracketed ID should be stripped before translation
        assert "https://" not in trans_kwargs["json"]["messages"][1]["content"]
        assert "[ID:" not in trans_kwargs["json"]["messages"][1]["content"]

        # Call 2: Bulbul TTS receives the translated Hindi Devanagari text, NOT English
        tts_args, tts_kwargs = mock_post.call_args_list[1]
        assert tts_args[0] == "https://api.sarvam.ai/text-to-speech"
        assert tts_kwargs["json"]["model"] == "bulbul:v3"
        assert tts_kwargs["json"]["speaker"] == "shubh"
        assert tts_kwargs["json"]["target_language_code"] == "hi-IN"
        assert tts_kwargs["json"]["text"] == hindi_translation


def test_tts_marathi_selection_translates_english_answer_before_bulbul():
    marathi_translation = (
        "जयपूरच्या ब्लू पॉटरीमध्ये नैसर्गिक मातीचा वापर केला जात नाही. तिचा गोळा क्वार्ट्झ दगडाची पावडर, "
        "काचेची पावडर, मुलतानी माती आणि कटिरा डिंकापासून तयार केला जातो."
    )
    mock_chat_resp = _make_chat_response(marathi_translation)
    mock_bulbul_resp = _make_bulbul_response()

    with patch("backend.tts.httpx.post", side_effect=[mock_chat_resp, mock_bulbul_resp]) as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": (
                    "Jaipur Blue Pottery does not use natural clay. Its dough is prepared from "
                    "powdered quartz stone, powdered glass, Multani Mitti, and Katira Gond."
                ),
                "target_language_code": "mr-IN",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_language_code"] == "mr-IN"
        assert data["model"] == "bulbul:v3"
        assert data["speaker"] == "shubh"
        assert data["translated"] is True
        assert data["spoken_text"] == marathi_translation

        # Verify Bulbul TTS request receives the translated Marathi text
        assert mock_post.call_count == 2
        trans_args, trans_kwargs = mock_post.call_args_list[0]
        assert trans_args[0] == "https://api.sarvam.ai/v1/chat/completions"
        assert "Marathi" in trans_kwargs["json"]["messages"][0]["content"]

        tts_args, tts_kwargs = mock_post.call_args_list[1]
        assert tts_args[0] == "https://api.sarvam.ai/text-to-speech"
        assert tts_kwargs["json"]["target_language_code"] == "mr-IN"
        assert tts_kwargs["json"]["text"] == marathi_translation


def test_tts_english_selection_synthesizes_directly_without_translation():
    mock_bulbul_resp = _make_bulbul_response()

    with patch("backend.tts.httpx.post", return_value=mock_bulbul_resp) as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": (
                    "Jaipur Blue Pottery uses powdered quartz stone and Katira Gond.\n\n"
                    "Source: D'source | https://www.dsource.in/resource [ID: src-blue-pottery-dsource-01]"
                ),
                "target_language_code": "en-IN",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_language_code"] == "en-IN"
        assert data["translated"] is False
        assert "Jaipur Blue Pottery uses powdered quartz stone" in data["spoken_text"]
        assert "https://" not in data["spoken_text"]

        # Only 1 call directly to Bulbul TTS
        assert mock_post.call_count == 1
        tts_args, tts_kwargs = mock_post.call_args
        assert tts_args[0] == "https://api.sarvam.ai/text-to-speech"
        assert tts_kwargs["json"]["target_language_code"] == "en-IN"
        assert tts_kwargs["json"]["model"] == "bulbul:v3"
        assert tts_kwargs["json"]["speaker"] == "shubh"


def test_tts_refuses_no_source_fallback():
    with patch("backend.tts.httpx.post") as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": NO_SOURCE_FALLBACK,
                "target_language_code": "hi-IN",
            },
        )
        assert resp.status_code == 400
        assert "Refusing to synthesize speech for the no-source fallback" in resp.json()["detail"]
        mock_post.assert_not_called()


def test_tts_translation_failure_does_not_silently_fallback_to_english():
    mock_trans_fail = MagicMock()
    mock_trans_fail.status_code = 500
    mock_trans_fail.text = "Upstream translation service unavailable"

    with patch("backend.tts.httpx.post", return_value=mock_trans_fail) as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": "Paithani sarees use three shuttles for Kadiyal border interlocking.",
                "target_language_code": "mr-IN",
            },
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "Sarvam translation error for Marathi (500)" in detail
        assert "sk_" not in detail
        # Must NOT proceed to call Bulbul TTS with English text when translation fails
        assert mock_post.call_count == 1


def test_tts_upstream_api_failure():
    mock_chat_ok = _make_chat_response("पैठणी साडीमध्ये तीन धोटे वापरले जातात.")
    mock_tts_fail = MagicMock()
    mock_tts_fail.status_code = 502
    mock_tts_fail.text = "Bad Gateway from Bulbul upstream"

    with patch("backend.tts.httpx.post", side_effect=[mock_chat_ok, mock_tts_fail]):
        resp = client.post(
            "/api/tts",
            json={
                "text": "Three shuttles are used in a Paithani saree.",
                "target_language_code": "mr-IN",
            },
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "Sarvam Bulbul TTS API error (502)" in detail
        assert "sk_" not in detail
