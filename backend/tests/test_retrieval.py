import json
from pathlib import Path
from backend.retrieval import load_archive, search_archive, get_lesson


def test_archive_contains_real_sourced_entries_without_invented_artisans():
    entries = load_archive()
    assert len(entries) >= 4
    crafts = {e["craft"] for e in entries}
    assert "Blue Pottery" in crafts
    assert "Paithani Weaving" in crafts

    for entry in entries:
        assert entry.get("verification_status") == "verified"
        assert entry.get("is_demo") is False
        assert entry.get("source_title") and len(entry["source_title"].strip()) > 5
        assert entry.get("source_organization") and len(entry["source_organization"].strip()) > 3
        assert entry.get("source_url", "").startswith(("http://", "https://"))
        assert isinstance(entry.get("supported_facts"), list) and len(entry["supported_facts"]) >= 3
        assert entry.get("excerpt") and len(entry["excerpt"].strip()) > 20
        # Seeded institutional records must not invent artisan names or fake audio recordings
        if entry.get("record_type") == "institutional_documentation":
            assert entry.get("artisan_name") is None
            assert entry.get("source_audio") is None


def test_known_query_returns_expected_entry_source_url_and_citation():
    # Query about Blue Pottery clay-free quartz dough and Katira Gond
    results = search_archive(
        "Why is Blue Pottery clay-free and how are quartz powder, Multani Mitti, and Katira Gond mixed?",
        craft="Blue Pottery",
    )
    assert len(results) >= 1
    top = results[0]
    assert top["id"] == "src-blue-pottery-dsource-01"
    assert "D'source" in top["citation"]
    assert "https://www.dsource.in/resource/blue-pottery-jaipur/making-process" in top["citation"]

    # Query about Paithani Kadiyal border shuttles and tilli bobbins
    paithani_results = search_archive("Kadiyal border interlocking three shuttles tilli bobbins")
    assert len(paithani_results) >= 1
    assert paithani_results[0]["id"] == "src-paithani-craftmark-02"
    assert "Craftmark" in paithani_results[0]["citation"]
    assert "http://www.craftmark.org/cms/public/uploads/1595673685.pdf" in paithani_results[0]["citation"]


def test_unverified_needs_source_entry_is_excluded_from_search(tmp_path: Path):
    temp_archive = tmp_path / "unverified_archive.json"
    records = [
        {
            "id": "unverified-claim-01",
            "record_type": "institutional_documentation",
            "verification_status": "needs_source",
            "craft": "Blue Pottery",
            "technique": "Unverified supersonic laser sintering glaze",
            "source_title": None,
            "source_organization": None,
            "source_url": None,
            "supported_facts": [],
            "steps": ["Apply laser sintering glaze"],
            "materials": ["Laser sintering powder"],
            "artisan_name": None,
            "language": "en-IN",
            "source_audio": None,
            "segment": "Unverified",
            "excerpt": "Unverified claim about supersonic laser sintering glaze.",
            "transcript": "Unverified claim about supersonic laser sintering glaze.",
            "is_demo": False,
        }
    ]
    temp_archive.write_text(json.dumps(records), encoding="utf-8")

    hits = search_archive(
        "supersonic laser sintering glaze",
        craft="Blue Pottery",
        archive_path=temp_archive,
    )
    assert hits == []


def test_unrelated_query_returns_no_evidence():
    # Unrelated craft query
    assert search_archive("How to carve Channapatna wooden toys with lacquer?") == []

    # Unanswerable query within a known craft (mentions Blue Pottery, but asks about unrecorded export price / GST)
    assert search_archive("What is the online export price and GST for Blue Pottery?", craft="Blue Pottery") == []


def test_get_lesson_includes_citations_source_links_and_supported_facts():
    archive = load_archive()
    blue_pottery_source = next(e for e in archive if e["id"] == "src-blue-pottery-dsource-01")

    lesson_resp = get_lesson("Blue Pottery", technique="Quartz Dough")
    assert lesson_resp["found"] is True
    assert len(lesson_resp["citations"]) == 1
    assert "D'source" in lesson_resp["citations"][0]
    assert len(lesson_resp["source_links"]) == 1
    assert lesson_resp["source_links"][0]["source_url"] == blue_pottery_source["source_url"]

    lesson = lesson_resp["lessons"][0]
    assert lesson["steps"] == blue_pottery_source["steps"]
    assert lesson["materials"] == blue_pottery_source["materials"]
    assert lesson["supported_facts"] == blue_pottery_source["supported_facts"]
    assert lesson["source_url"] == blue_pottery_source["source_url"]
    assert lesson["artisan_name"] is None

    # Requesting a non-existent technique or craft returns no invented data and exact no-source fallback
    missing_lesson = get_lesson("Blue Pottery", technique="Electric Wheel Throwing")
    assert missing_lesson["found"] is False
    assert missing_lesson["lessons"] == []
    assert missing_lesson["citations"] == []
    assert missing_lesson["source_links"] == []
    assert missing_lesson["message"] == "Mere paas iska source nahi hai."
