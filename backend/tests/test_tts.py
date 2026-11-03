from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.qa import NO_SOURCE_FALLBACK

client = TestClient(app)


def test_tts_successful_audio_generation():
    mock_bulbul_resp = MagicMock()
    mock_bulbul_resp.status_code = 200
    mock_bulbul_resp.json.return_value = {
        "request_id": "tts-req-001",
        "audios": ["UklGRvAZAwBXQVZFZm10IBAAAAABAA=="],
    }

    with patch("backend.tts.httpx.post", return_value=mock_bulbul_resp) as mock_post:
        resp = client.post(
            "/api/tts",
            json={
                "text": "Jaipur Blue Pottery mein 40 hissa quartz stone aur 5 hissa katira gond milate hain.",
                "target_language_code": "hi-IN",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_base64"] == "UklGRvAZAwBXQVZFZm10IBAAAAABAA=="
        assert data["mime_type"] == "audio/wav"
        assert data["model"] == "bulbul:v3"
        assert data["speaker"] == "shubh"
        assert "sk_" not in str(data)

        # Verify request sent to official Bulbul endpoint
        called_args, called_kwargs = mock_post.call_args
        assert called_args[0] == "https://api.sarvam.ai/text-to-speech"
        assert called_kwargs["json"]["model"] == "bulbul:v3"
        assert called_kwargs["json"]["target_language_code"] == "hi-IN"


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


def test_tts_upstream_api_failure():
    mock_fail = MagicMock()
    mock_fail.status_code = 502
    mock_fail.text = "Bad Gateway from Bulbul upstream"

    with patch("backend.tts.httpx.post", return_value=mock_fail):
        resp = client.post(
            "/api/tts",
            json={
                "text": "Paithani saadi madhe teen dhote vaparle jatat.",
                "target_language_code": "mr-IN",
            },
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "Sarvam Bulbul TTS API error (502)" in detail
        assert "sk_" not in detail
