import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_ARCHIVE_PATH = Path(__file__).resolve().parent / "data" / "archive.json"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
    "for", "from", "how", "i", "in", "is", "it", "many", "much", "of",
    "on", "or", "should", "tell", "that", "the", "their", "there", "these",
    "they", "this", "to", "us", "use", "used", "using", "was", "we", "what",
    "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your", "about", "into", "after", "before", "make", "made", "making",
    # Hindi / Marathi common function words (transliterated)
    "ka", "ki", "ke", "ko", "se", "mein", "hai", "hain", "aur", "kya",
    "kaise", "kahan", "kab", "kaun", "kitna", "kitne", "kuch", "bhi",
    "par", "pe", "tak", "ye", "woh", "jo", "toh", "na", "nahi", "ek",
    "aani", "var", "madhe", "kase", "kay", "kiti", "kon", "he", "te"
}

# Generic craft / domain terms that alone should not trigger a match
# if the query asks about an unrecorded topic.
GENERIC_CRAFT_TERMS = {
    "blue", "pottery", "jaipur", "paithani", "weaving", "yeola",
    "saree", "saadi", "craft", "crafts", "artisan", "artisans",
    "traditional", "indian", "handloom", "handmade", "art", "work"
}


def load_archive(archive_path: Optional[Path] = None) -> list[dict[str, Any]]:
    path = Path(archive_path) if archive_path else DEFAULT_ARCHIVE_PATH
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def format_citation(entry: dict[str, Any]) -> str:
    entry_id = entry.get("id", "unknown_id")
    segment = entry.get("segment") or "Documented Section"
    artisan = entry.get("artisan_name")
    audio = entry.get("source_audio")
    source_title = entry.get("source_title")
    source_org = entry.get("source_organization")
    source_url = entry.get("source_url")

    if artisan and audio:
        url_part = f" | {source_url}" if source_url else ""
        return f"{artisan} — {audio}, {segment}{url_part} [ID: {entry_id}]"

    if source_title:
        org_part = f" — {source_org}" if source_org else ""
        url_part = f" | {source_url}" if source_url else ""
        return f"{source_title}{org_part} ({segment}){url_part} [ID: {entry_id}]"

    return f"{artisan or 'Unknown Source'} — {audio or 'unknown_source'}, {segment} [ID: {entry_id}]"


def _normalize_token(token: str) -> str:
    """Simple suffix normalization so plurals/gerunds match base words."""
    t = token.lower().strip()
    if len(t) > 5 and t.endswith("ing"):
        # e.g., firing -> fir (matches fire -> fir), weaving -> weav
        return t[:-3]
    if len(t) > 4 and t.endswith("ed"):
        return t[:-2]
    if len(t) > 4 and t.endswith("es"):
        return t[:-2]
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    if len(t) > 4 and t.endswith("e"):
        return t[:-1]
    return t


def _tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-zA-Z0-9\u0900-\u097F]+", text.lower())
    return [t for t in raw_tokens if len(t) > 1 and t not in STOPWORDS]


def _entry_searchable_tokens(entry: dict[str, Any]) -> set[str]:
    fields = [
        str(entry.get("technique") or ""),
        " ".join(entry.get("steps") or []),
        " ".join(entry.get("materials") or []),
        " ".join(entry.get("supported_facts") or []),
        str(entry.get("excerpt") or ""),
        str(entry.get("transcript") or ""),
        str(entry.get("source_title") or ""),
        str(entry.get("source_organization") or ""),
        str(entry.get("artisan_name") or ""),
    ]
    combined = " ".join(fields)
    raw = _tokenize(combined)
    normalized = {_normalize_token(t) for t in raw}
    return set(raw) | normalized


def search_archive(
    query: str,
    craft: Optional[str] = None,
    archive_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """
    Search archive entries using keyword matching.
    Excludes any entry marked with verification_status == 'needs_source'.
    Returns matching entries sorted by relevance score, each enriched with a 'citation' field.
    If no specific evidence matches the query, returns an empty list [].
    """
    if not query or not query.strip():
        return []

    entries = [
        e for e in load_archive(archive_path)
        if e.get("verification_status", "verified") != "needs_source"
    ]
    if craft:
        craft_clean = craft.strip().lower()
        entries = [
            e for e in entries
            if e.get("craft", "").strip().lower() == craft_clean
        ]

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Separate unique specific content tokens from generic craft-title tokens
    specific_tokens = list(dict.fromkeys(t for t in query_tokens if t not in GENERIC_CRAFT_TERMS))
    if not specific_tokens:
        # Query only mentioned the craft name without any specific question/keyword
        return []

    results: list[dict[str, Any]] = []

    for entry in entries:
        entry_tokens = _entry_searchable_tokens(entry)
        matched_specific = []
        for qt in specific_tokens:
            norm_qt = _normalize_token(qt)
            if qt in entry_tokens or norm_qt in entry_tokens:
                matched_specific.append(qt)

        if not matched_specific:
            continue

        # Calculate match ratio and score to avoid false positives when a query
        # asks about an unrecorded topic but shares a stray word.
        score = len(matched_specific)
        match_ratio = len(matched_specific) / len(specific_tokens)

        # Require sufficient keyword coverage (>= 35% of unique specific query terms)
        # and either >= 2 matched terms or >= 50% ratio
        if match_ratio >= 0.35 and (score >= 2 or match_ratio >= 0.5):
            enriched = dict(entry)
            enriched["citation"] = format_citation(entry)
            enriched["matched_terms"] = matched_specific
            enriched["score"] = round(score + match_ratio, 3)
            results.append(enriched)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_lesson(
    craft: str,
    technique: Optional[str] = None,
    archive_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Assemble a structured lesson strictly from verified archived entries for the given craft
    (and optional technique filter), preserving citations, source URLs, and supported facts.
    """
    if not craft or not craft.strip():
        return {
            "craft": craft,
            "technique": technique,
            "found": False,
            "message": "Mere paas iska source nahi hai.",
            "lessons": [],
            "citations": [],
            "source_links": [],
        }

    entries = [
        e for e in load_archive(archive_path)
        if e.get("verification_status", "verified") != "needs_source"
    ]
    craft_clean = craft.strip().lower()
    matched = [
        e for e in entries
        if e.get("craft", "").strip().lower() == craft_clean
    ]

    if technique and technique.strip():
        tech_tokens = _tokenize(technique)
        filtered = []
        for e in matched:
            tech_text = (
                str(e.get("technique") or "") + " " +
                str(e.get("excerpt") or "") + " " +
                str(e.get("transcript") or "")
            ).lower()
            entry_tech_tokens = _entry_searchable_tokens(e)
            if technique.strip().lower() in tech_text or (
                tech_tokens and all(
                    (t in entry_tech_tokens or _normalize_token(t) in entry_tech_tokens)
                    for t in tech_tokens
                )
            ):
                filtered.append(e)
        matched = filtered

    if not matched:
        return {
            "craft": craft,
            "technique": technique,
            "found": False,
            "message": "Mere paas iska source nahi hai.",
            "lessons": [],
            "citations": [],
            "source_links": [],
        }

    lessons = []
    citations = []
    source_links = []
    for entry in matched:
        cite = format_citation(entry)
        citations.append(cite)
        if entry.get("source_url"):
            source_links.append({
                "entry_id": entry["id"],
                "source_title": entry.get("source_title"),
                "source_organization": entry.get("source_organization"),
                "source_url": entry.get("source_url"),
            })
        lessons.append({
            "entry_id": entry["id"],
            "record_type": entry.get("record_type", "institutional_documentation" if entry.get("source_title") else "oral_contribution"),
            "verification_status": entry.get("verification_status", "verified"),
            "craft": entry["craft"],
            "technique": entry["technique"],
            "source_title": entry.get("source_title"),
            "source_organization": entry.get("source_organization"),
            "source_url": entry.get("source_url"),
            "supported_facts": list(entry.get("supported_facts", [])),
            "excerpt": entry.get("excerpt") or entry.get("transcript", ""),
            "artisan_name": entry.get("artisan_name"),
            "language": entry.get("language", "en-IN"),
            "steps": list(entry.get("steps", [])),
            "materials": list(entry.get("materials", [])),
            "transcript": entry.get("transcript", ""),
            "source_audio": entry.get("source_audio"),
            "segment": entry.get("segment", ""),
            "is_demo": bool(entry.get("is_demo", False)),
            "citation": cite,
        })

    return {
        "craft": matched[0]["craft"],
        "technique": technique,
        "found": True,
        "lessons": lessons,
        "citations": citations,
        "source_links": source_links,
    }


def _normalize_string_list(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        parts = re.split(r"[\n,;]+", val)
        return [p.strip() for p in parts if p.strip()]
    return []


def add_oral_entry(
    entry: dict[str, Any],
    archive_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Validate and save a reviewed artisan contribution to the JSON archive.
    Required fields: craft, technique, artisan_name, transcript, source_audio, segment.
    """
    if not isinstance(entry, dict):
        raise ValueError("Entry must be a JSON object.")

    required_fields = ["craft", "technique", "artisan_name", "transcript", "source_audio", "segment"]
    for field in required_fields:
        val = entry.get(field)
        if not val or not str(val).strip():
            raise ValueError(f"Missing or empty required field: '{field}'")

    path = Path(archive_path) if archive_path else DEFAULT_ARCHIVE_PATH
    entries = load_archive(path)

    entry_id = str(entry.get("id", "")).strip() or f"oral-{uuid.uuid4().hex[:8]}"
    language = str(entry.get("language", "hi-IN")).strip() or "hi-IN"
    created_at = str(entry.get("created_at", "")).strip() or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    transcript_str = str(entry["transcript"]).strip()
    artisan_str = str(entry["artisan_name"]).strip()
    audio_str = str(entry["source_audio"]).strip()
    segment_str = str(entry["segment"]).strip()
    source_title = str(entry.get("source_title") or f"Oral Recording by {artisan_str}").strip()
    source_org = str(entry.get("source_organization") or "KalaSetu Reviewed Artisan Audio Contribution").strip()
    source_url = str(entry.get("source_url") or "").strip() or None
    verification_status = (
        "needs_source"
        if entry.get("verification_status") == "needs_source" or entry.get("needs_source") is True
        else "verified"
    )

    new_record: dict[str, Any] = {
        "id": entry_id,
        "record_type": str(entry.get("record_type") or "oral_contribution"),
        "verification_status": verification_status,
        "craft": str(entry["craft"]).strip(),
        "technique": str(entry["technique"]).strip(),
        "source_title": source_title,
        "source_organization": source_org,
        "source_url": source_url,
        "supported_facts": _normalize_string_list(entry.get("supported_facts")) or _normalize_string_list(entry.get("steps")),
        "steps": _normalize_string_list(entry.get("steps")),
        "materials": _normalize_string_list(entry.get("materials")),
        "artisan_name": artisan_str,
        "language": language,
        "source_audio": audio_str,
        "segment": segment_str,
        "excerpt": str(entry.get("excerpt") or transcript_str).strip(),
        "transcript": transcript_str,
        "created_at": created_at,
        "is_demo": bool(entry.get("is_demo", False)),
    }

    entries.append(new_record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    enriched = dict(new_record)
    enriched["citation"] = format_citation(new_record)
    return enriched

