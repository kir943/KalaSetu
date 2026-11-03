from unittest.mock import patch, MagicMock
from pathlib import Path
from fastapi.testclient import TestClient

from backend.main import app
from backend.retrieval import add_oral_entry, load_archive, search_archive

client = TestClient(app)


def test_invalid_audio_upload_rejected():
    # 1. Invalid file extension (.txt instead of audio)
    resp_ext = client.post(
        "/api/transcribe",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
        data={"language_code": "hi-IN"},
    )
    assert resp_ext.status_code == 400
    assert "Unsupported audio format" in resp_ext.json()["detail"]

    # 2. Empty audio file
    resp_empty = client.post(
        "/api/transcribe",
        files={"file": ("empty_clip.wav", b"", "audio/wav")},
        data={"language_code": "hi-IN"},
    )
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower()

    # 3. Unsupported language code
    resp_lang = client.post(
        "/api/transcribe",
        files={"file": ("clip.wav", b"RIFF1234WAVE", "audio/wav")},
        data={"language_code": "fr-FR"},
    )
    assert resp_lang.status_code == 400
    assert "Unsupported language_code" in resp_lang.json()["detail"]


def test_transcription_error_handling():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service temporarily unavailable"

    with patch("backend.saaras.httpx.post", return_value=mock_resp):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("artisan_voice.wav", b"RIFF_DUMMY_AUDIO_BYTES", "audio/wav")},
            data={"language_code": "hi-IN"},
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "Sarvam Saaras API error (503)" in detail
        assert "sk_" not in detail


def test_transcription_success_with_and_without_timestamps():
    # Case A: Saaras returns word-level timestamps
    mock_with_ts = MagicMock()
    mock_with_ts.status_code = 200
    mock_with_ts.json.return_value = {
        "request_id": "req-123",
        "transcript": "Neela rang cobalt oxide se banta hai.",
        "language_code": "hi-IN",
        "timestamps": {
            "words": ["Neela", "rang", "cobalt", "oxide", "se", "banta", "hai"],
            "start_time_seconds": [0.2, 0.6, 1.1, 1.7, 2.2, 2.5, 3.0],
            "end_time_seconds": [0.5, 1.0, 1.6, 2.1, 2.4, 2.9, 3.4],
        },
    }

    with patch("backend.saaras.httpx.post", return_value=mock_with_ts):
        resp = client.post(
            "/api/transcribe",
            files={"file": ("ramesh_glaze.wav", b"RIFF_DUMMY_AUDIO", "audio/wav")},
            data={"language_code": "hi-IN"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["transcript"] == "Neela rang cobalt oxide se banta hai."
        assert data["has_exact_timestamps"] is True
        assert data["segment"] == "Segment 1 (0.2s - 3.4s)"
        assert data["source_audio"] == "ramesh_glaze.wav"

    # Case B: Saaras returns empty timestamps -> must use chunk-level label and never invent timestamps
    mock_no_ts = MagicMock()
    mock_no_ts.status_code = 200
    mock_no_ts.json.return_value = {
        "request_id": "req-456",
        "transcript": "Kadiyal kathasathi teen dhote vapartat.",
        "language_code": "mr-IN",
        "timestamps": {"words": [], "start_time_seconds": [], "end_time_seconds": []},
    }

    with patch("backend.saaras.httpx.post", return_value=mock_no_ts):
        resp2 = client.post(
            "/api/transcribe",
            files={"file": ("shantabai_clip.wav", b"RIFF_DUMMY_AUDIO", "audio/wav")},
            data={"language_code": "mr-IN"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["has_exact_timestamps"] is False
        assert "Chunk 1" in data2["segment"]
        assert "timestamps not returned" in data2["segment"]


def test_save_reviewed_entry_and_persistence(tmp_path: Path):
    temp_archive = tmp_path / "test_archive.json"
    temp_archive.write_text("[]", encoding="utf-8")

    # 1. Saving via add_oral_entry persists and is searchable with citation
    saved = add_oral_entry(
        {
            "craft": "Blue Pottery",
            "technique": "Turquoise Copper Oxide Glaze",
            "artisan_name": "Gopal Saini",
            "language": "hi-IN",
            "transcript": "Firozi rang banane ke liye copper oxide ko kaanch ke powder mein milate hain.",
            "steps": "Grind copper oxide\nMix with powdered glass slip",
            "materials": "Copper oxide, Powdered glass",
            "source_audio": "gopal_firozi_clip.wav",
            "segment": "Chunk 1 (Full uploaded audio clip — timestamps not returned by Saaras)",
        },
        archive_path=temp_archive,
    )

    assert saved["id"].startswith("oral-")
    assert saved["steps"] == ["Grind copper oxide", "Mix with powdered glass slip"]
    assert saved["materials"] == ["Copper oxide", "Powdered glass"]
    assert "Gopal Saini — gopal_firozi_clip.wav" in saved["citation"]

    # Verify persisted to disk and retrievable via search_archive
    persisted = load_archive(temp_archive)
    assert len(persisted) == 1
    hits = search_archive("How to make firozi rang with copper oxide?", craft="Blue Pottery", archive_path=temp_archive)
    assert len(hits) == 1
    assert hits[0]["artisan_name"] == "Gopal Saini"
    assert "gopal_firozi_clip.wav" in hits[0]["citation"]

    # 2. Test FastAPI POST /api/entries endpoint with patched DEFAULT_ARCHIVE_PATH
    with patch("backend.retrieval.DEFAULT_ARCHIVE_PATH", temp_archive):
        api_resp = client.post(
            "/api/entries",
            json={
                "craft": "Paithani Weaving",
                "technique": "Asavali Floral Motif Weaving",
                "artisan_name": "Meera Joshi",
                "language": "mr-IN",
                "transcript": "Asavali phulanchi nakshi chandi aani sonyachya zari ne vinli jate.",
                "steps": ["Prepare silk warp", "Interlock Asavali motif with zari"],
                "materials": ["Mulberry silk", "Gold zari"],
                "source_audio": "meera_asavali.wav",
                "segment": "Segment 1 (0.0s - 12.5s)",
            },
        )
        assert api_resp.status_code == 201
        body = api_resp.json()
        assert body["artisan_name"] == "Meera Joshi"
        assert "meera_asavali.wav" in body["citation"]
        assert len(load_archive(temp_archive)) == 2
