from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.qa import NO_SOURCE_FALLBACK, run_grounding_benchmark

client = TestClient(app)


def test_grounded_answer_and_citation_presence():
    mock_llm_resp = MagicMock()
    mock_llm_resp.status_code = 200
    mock_llm_resp.json.return_value = {
        "id": "chatcmpl-test-1",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "In Jaipur Blue Pottery, 40 parts powdered quartz stone, 5 parts katira gum, "
                        "and 2 parts multani mitti are mixed with water without regular potter's clay."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }

    with patch("backend.qa.httpx.post", return_value=mock_llm_resp):
        resp = client.post(
            "/api/ask",
            json={
                "question": "How many parts of powdered quartz stone and katira gum are mixed?",
                "craft": "Blue Pottery",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is True
        assert "40 parts powdered quartz stone" in data["answer"]
        # Every answer must show the source artisan, recording, and segment
        assert "Ramesh Kumar Kumhar (DEMO)" in data["answer"]
        assert "demo_ramesh_blue_pottery_seg1.wav" in data["answer"]
        assert "Segment 1 (00:00 - 01:15)" in data["answer"]
        assert len(data["citations"]) == 1
        assert len(data["sources"]) == 1


def test_no_source_fallback_when_no_evidence():
    # Unanswerable query must return exact fallback without inventing citations
    resp = client.post(
        "/api/ask",
        json={
            "question": "What is the wholesale export price and GST tax rate for Blue Pottery vases?",
            "craft": "Blue Pottery",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["grounded"] is False
    assert data["answer"] == NO_SOURCE_FALLBACK
    assert data["citations"] == []
    assert data["sources"] == []


def test_api_failure_kept_distinct_from_no_source_fallback():
    mock_fail = MagicMock()
    mock_fail.status_code = 500
    mock_fail.text = "Internal Server Error"

    with patch("backend.qa.httpx.post", return_value=mock_fail):
        resp = client.post(
            "/api/ask",
            json={
                "question": "How many parts of quartz stone and katira gum are used?",
                "craft": "Blue Pottery",
            },
        )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "Sarvam-105B API error (500)" in detail
        assert NO_SOURCE_FALLBACK not in detail
        assert "sk_" not in detail


def test_ten_question_grounding_suite_passes_100_percent():
    report = run_grounding_benchmark(use_llm=False)
    assert report["total"] == 10
    assert report["passed"] == 10
    assert report["pass_rate"] == "10/10 (100%)"
    answerable_cases = [r for r in report["results"] if r["expected_answerable"]]
    unanswerable_cases = [r for r in report["results"] if not r["expected_answerable"]]
    assert len(answerable_cases) == 5
    assert len(unanswerable_cases) == 5
    for r in report["results"]:
        assert r["passed"] is True
