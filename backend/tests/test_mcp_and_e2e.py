from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.mcp_server import handle_jsonrpc_message, list_mcp_tools
from backend.qa import NO_SOURCE_FALLBACK

client = TestClient(app)


def test_mcp_tools_independently(tmp_path: Path):
    # Prepare isolated archive seeded from existing demo entries
    orig = Path("backend/data/archive.json").read_text(encoding="utf-8")
    temp_archive = tmp_path / "mcp_archive.json"
    temp_archive.write_text(orig, encoding="utf-8")

    # 1. Verify tools/list returns all 3 required tools
    list_resp = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert tool_names == ["search_archive", "add_oral_entry", "get_lesson"]

    # 2. Test MCP tool 1: search_archive
    search_resp = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_archive",
                "arguments": {"query": "powdered quartz stone katira gum", "craft": "Blue Pottery"},
            },
        },
        archive_path=temp_archive,
    )
    assert search_resp["result"]["isError"] is False
    hits = search_resp["result"]["structuredContent"]
    assert len(hits) == 1
    assert hits[0]["id"] == "demo-blue-pottery-01"
    assert "Ramesh Kumar Kumhar (DEMO)" in hits[0]["citation"]

    # 3. Test MCP tool 2: add_oral_entry
    add_resp = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_oral_entry",
                "arguments": {
                    "entry": {
                        "craft": "Blue Pottery",
                        "technique": "camel hair squirrel brush painting",
                        "artisan_name": "Kishan Lal",
                        "language": "hi-IN",
                        "transcript": "Phool patti ki barik design gilahari ke baal wale brush se banate hain.",
                        "steps": ["Prepare squirrel hair brush", "Paint cobalt floral outlines"],
                        "materials": ["Squirrel hair brush (gilahari brush)", "Cobalt oxide"],
                        "source_audio": "kishan_brush_clip.wav",
                        "segment": "Segment 1 (0.0s - 18.0s)",
                    }
                },
            },
        },
        archive_path=temp_archive,
    )
    assert add_resp["result"]["isError"] is False
    added_entry = add_resp["result"]["structuredContent"]
    assert added_entry["artisan_name"] == "Kishan Lal"
    assert "kishan_brush_clip.wav" in added_entry["citation"]

    # 4. Test MCP tool 3: get_lesson
    lesson_resp = handle_jsonrpc_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "get_lesson",
                "arguments": {"craft": "Blue Pottery", "technique": "squirrel brush"},
            },
        },
        archive_path=temp_archive,
    )
    assert lesson_resp["result"]["isError"] is False
    lesson_data = lesson_resp["result"]["structuredContent"]
    assert lesson_data["found"] is True
    assert len(lesson_data["lessons"]) == 1
    assert "Kishan Lal — kishan_brush_clip.wav, Segment 1 (0.0s - 18.0s)" in lesson_data["citations"][0]


def test_complete_end_to_end_demo_flow(tmp_path: Path):
    orig = Path("backend/data/archive.json").read_text(encoding="utf-8")
    temp_archive = tmp_path / "e2e_archive.json"
    temp_archive.write_text(orig, encoding="utf-8")

    with patch("backend.retrieval.DEFAULT_ARCHIVE_PATH", temp_archive):
        # Step 1: Upload audio -> transcribe via Saaras
        mock_stt = MagicMock()
        mock_stt.status_code = 200
        mock_stt.json.return_value = {
            "request_id": "stt-e2e-1",
            "transcript": "Chandi ki zari ko sone ke paani mein dubokar 24 karat banaya jata hai.",
            "language_code": "mr-IN",
            "timestamps": {
                "words": ["Chandi", "ki", "zari"],
                "start_time_seconds": [0.5, 1.0, 1.5],
                "end_time_seconds": [0.9, 1.4, 4.2],
            },
        }
        with patch("backend.saaras.httpx.post", return_value=mock_stt):
            tr_resp = client.post(
                "/api/transcribe",
                files={"file": ("vasant_zari_process.wav", b"RIFF_WAVE_DATA", "audio/wav")},
                data={"language_code": "mr-IN"},
            )
            assert tr_resp.status_code == 200
            tr_data = tr_resp.json()
            assert tr_data["segment"] == "Segment 1 (0.5s - 4.2s)"

        # Step 2: Review and save entry to archive
        save_resp = client.post(
            "/api/entries",
            json={
                "craft": "Paithani Weaving",
                "technique": "Gold Plating of Silver Zari Threads",
                "artisan_name": "Vasantrao Deshmukh",
                "language": tr_data["language_code"],
                "transcript": tr_data["transcript"],
                "steps": ["Draw pure silver wire", "Electroplate in 24-karat gold bath"],
                "materials": ["Pure silver wire (chandi)", "24-karat gold bath (sone ka paani)"],
                "source_audio": tr_data["source_audio"],
                "segment": tr_data["segment"],
            },
        )
        assert save_resp.status_code == 201
        saved_entry = save_resp.json()
        assert "Vasantrao Deshmukh — vasant_zari_process.wav, Segment 1 (0.5s - 4.2s)" in saved_entry["citation"]

        # Step 3: Ask an answerable question and confirm citation
        mock_chat = MagicMock()
        mock_chat.status_code = 200
        mock_chat.json.return_value = {
            "id": "chat-e2e-1",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": (
                            "According to Vasantrao Deshmukh, silver zari wire is dipped in a 24-karat gold bath "
                            "(vasant_zari_process.wav, Segment 1 (0.5s - 4.2s))."
                        ),
                    },
                    "finish_reason": "stop",
                }
            ],
        }
        with patch("backend.qa.httpx.post", return_value=mock_chat):
            ask_ok = client.post(
                "/api/ask",
                json={
                    "question": "How is silver zari dipped in sone ka paani gold bath?",
                    "craft": "Paithani Weaving",
                },
            )
            assert ask_ok.status_code == 200
            ask_ok_data = ask_ok.json()
            assert ask_ok_data["grounded"] is True
            assert "Vasantrao Deshmukh" in ask_ok_data["answer"]
            assert "vasant_zari_process.wav" in ask_ok_data["answer"]
            assert "Segment 1 (0.5s - 4.2s)" in ask_ok_data["answer"]

        # Step 4: Ask an unanswerable question -> confirm exact fallback
        ask_unans = client.post(
            "/api/ask",
            json={
                "question": "What is the customs import duty on Italian powerlooms?",
                "craft": "Paithani Weaving",
            },
        )
        assert ask_unans.status_code == 200
        ask_unans_data = ask_unans.json()
        assert ask_unans_data["grounded"] is False
        assert ask_unans_data["answer"] == NO_SOURCE_FALLBACK
        assert ask_unans_data["citations"] == []

        # Step 5: Click Listen -> confirm Bulbul audio returned for grounded answer
        mock_tts = MagicMock()
        mock_tts.status_code = 200
        mock_tts.json.return_value = {
            "request_id": "tts-e2e-1",
            "audios": ["UklGRvAZAwBXQVZFZm10IBAAAAABAA=="],
        }
        with patch("backend.tts.httpx.post", return_value=mock_tts):
            tts_resp = client.post(
                "/api/tts",
                json={
                    "text": ask_ok_data["answer"],
                    "target_language_code": "mr-IN",
                },
            )
            assert tts_resp.status_code == 200
            assert tts_resp.json()["audio_base64"].startswith("UklGR")
