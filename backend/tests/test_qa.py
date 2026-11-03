from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.qa import NO_SOURCE_FALLBACK, run_grounding_benchmark

client = TestClient(app)


def test_grounded_answer_citation_and_source_links_presence():
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
                        "Jaipur Blue Pottery does not use natural potter's clay; its dough is prepared from "
                        "powdered quartz stone, powdered glass, Multani Mitti (Fuller's Earth), Katira Gond "
                        "(gum tragacanth), and Sajikhar."
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
                "question": "Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed to prepare its dough?",
                "craft": "Blue Pottery",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["grounded"] is True
        assert "powdered quartz stone" in data["answer"]
        # Every answer must cite the supporting archive entry, publisher, and URL
        assert "Blue Pottery of Jaipur — Tools, Raw Materials, and Making Process" in data["answer"]
        assert "D'source" in data["answer"]
        assert "https://www.dsource.in/resource/blue-pottery-jaipur/making-process" in data["answer"]
        assert "src-blue-pottery-dsource-01" in data["answer"]
        assert len(data["citations"]) >= 1
        assert len(data["source_links"]) >= 1
        assert data["source_links"][0]["source_url"] == "https://www.dsource.in/resource/blue-pottery-jaipur/making-process"
        assert len(data["sources"]) >= 1
        assert len(data["sources"][0]["supported_facts"]) >= 3
        assert data["sources"][0]["excerpt"]


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
    assert data["source_links"] == []
    assert data["sources"] == []


def test_api_failure_kept_distinct_from_no_source_fallback():
    mock_fail = MagicMock()
    mock_fail.status_code = 500
    mock_fail.text = "Internal Server Error"

    with patch("backend.qa.httpx.post", return_value=mock_fail):
        resp = client.post(
            "/api/ask",
            json={
                "question": "Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed?",
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
