from backend.retrieval import load_archive, search_archive, get_lesson


def test_archive_has_two_labeled_demo_entries():
    entries = load_archive()
    assert len(entries) >= 2
    crafts = {e["craft"] for e in entries}
    assert "Blue Pottery" in crafts
    assert "Paithani Weaving" in crafts
    for entry in entries:
        assert entry.get("is_demo") is True
        assert "DEMO" in entry.get("artisan_name", "")


def test_known_query_returns_expected_entry_and_citation():
    # Query about Blue Pottery quartz and katira gum
    results = search_archive("How much quartz stone and katira gum is mixed?", craft="Blue Pottery")
    assert len(results) == 1
    top = results[0]
    assert top["id"] == "demo-blue-pottery-01"
    assert "Ramesh Kumar Kumhar (DEMO)" in top["citation"]
    assert "demo_ramesh_blue_pottery_seg1.wav" in top["citation"]
    assert "Segment 1" in top["citation"]

    # Query about Paithani Kadiyal shuttles (dhote) and Bangadi Mor
    paithani_results = search_archive("Kadiyal border teen dhote shuttles Bangadi Mor")
    assert len(paithani_results) == 1
    assert paithani_results[0]["id"] == "demo-paithani-01"
    assert "Shantabai Kulkarni (DEMO)" in paithani_results[0]["citation"]
    assert "Segment 2" in paithani_results[0]["citation"]


def test_unrelated_query_returns_no_evidence():
    # Unrelated craft query
    assert search_archive("How to carve Channapatna wooden toys with lacquer?") == []

    # Unanswerable query within a known craft (mentions Blue Pottery, but asks about unrecorded export price / GST)
    assert search_archive("What is the online export price and GST for Blue Pottery?", craft="Blue Pottery") == []


def test_get_lesson_includes_citations_and_does_not_invent_details():
    archive = load_archive()
    blue_pottery_source = next(e for e in archive if e["id"] == "demo-blue-pottery-01")

    lesson_resp = get_lesson("Blue Pottery", technique="Quartz Dough")
    assert lesson_resp["found"] is True
    assert len(lesson_resp["citations"]) == 1
    assert "Ramesh Kumar Kumhar (DEMO)" in lesson_resp["citations"][0]
    assert "Segment 1" in lesson_resp["citations"][0]

    lesson = lesson_resp["lessons"][0]
    # Verify exact match with source archive — no invented steps, materials, or transcript content
    assert lesson["steps"] == blue_pottery_source["steps"]
    assert lesson["materials"] == blue_pottery_source["materials"]
    assert lesson["transcript"] == blue_pottery_source["transcript"]
    assert lesson["artisan_name"] == blue_pottery_source["artisan_name"]

    # Requesting a non-existent technique or craft returns no invented data and exact no-source fallback
    missing_lesson = get_lesson("Blue Pottery", technique="Electric Wheel Throwing")
    assert missing_lesson["found"] is False
    assert missing_lesson["lessons"] == []
    assert missing_lesson["citations"] == []
    assert missing_lesson["message"] == "Mere paas iska source nahi hai."
