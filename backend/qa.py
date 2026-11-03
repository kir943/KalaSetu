import os
from pathlib import Path
from typing import Any, Optional
import httpx

from backend.retrieval import search_archive

SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_CHAT_MODEL = "sarvam-105b-conversations"
NO_SOURCE_FALLBACK = "Mere paas iska source nahi hai."


def _build_evidence_context(entries: list[dict[str, Any]]) -> str:
    blocks = []
    for idx, entry in enumerate(entries, start=1):
        steps_str = "; ".join(entry.get("steps") or [])
        materials_str = ", ".join(entry.get("materials") or [])
        facts_str = "; ".join(entry.get("supported_facts") or [])
        excerpt_text = entry.get("excerpt") or entry.get("transcript") or ""
        artisan_line = (
            f"Artisan Name: {entry['artisan_name']}\n"
            f"Source Recording: {entry.get('source_audio')}\n"
            if entry.get("artisan_name")
            else "Record Type: Institutional Documentation (Do NOT attribute to a fictional artisan)\n"
        )
        block = (
            f"[Source {idx} — ID: {entry.get('id')}]\n"
            f"Craft: {entry.get('craft')}\n"
            f"Technique: {entry.get('technique')}\n"
            f"Source Title: {entry.get('source_title') or 'Oral Archive Contribution'}\n"
            f"Organization/Publisher: {entry.get('source_organization') or 'KalaSetu Archive'}\n"
            f"Source URL: {entry.get('source_url') or 'N/A (Local Audio Recording)'}\n"
            f"{artisan_line}"
            f"Source Segment: {entry.get('segment')}\n"
            f"Citation: {entry.get('citation')}\n"
            f"Supported Facts: {facts_str}\n"
            f"Materials: {materials_str}\n"
            f"Steps: {steps_str}\n"
            f"Verified Excerpt / Transcript: {excerpt_text}\n"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def _synthesize_deterministic_grounded_answer(entries: list[dict[str, Any]]) -> str:
    """
    Constructs a strictly archive-backed summary from retrieved entries (used when
    use_llm=False in fast offline unit tests). Never invents artisan names or quotes.
    """
    parts = []
    for entry in entries:
        steps_str = " ".join(entry.get("steps") or [])
        materials_str = ", ".join(entry.get("materials") or [])
        facts_str = " ".join(entry.get("supported_facts") or [])
        excerpt_text = entry.get("excerpt") or entry.get("transcript") or ""

        if entry.get("artisan_name") and entry.get("source_audio"):
            parts.append(
                f"According to {entry['artisan_name']} ({entry['source_audio']}, {entry.get('segment', 'Segment 1')}): "
                f"{entry['technique']}. Materials: {materials_str}. Steps: {steps_str} "
                f"Transcript: \"{excerpt_text}\""
            )
        else:
            source_title = entry.get("source_title") or entry["id"]
            source_org = entry.get("source_organization") or "Institutional Source"
            segment = entry.get("segment") or "Documented Section"
            parts.append(
                f"According to {source_title} ({source_org}, {segment}): "
                f"{entry['technique']}. Supported facts: {facts_str} "
                f"Materials: {materials_str}. Steps: {steps_str} "
                f"Documented excerpt: \"{excerpt_text}\""
            )
    citations_str = " | ".join(e["citation"] for e in entries)
    return "\n\n".join(parts) + f"\n\nSource: {citations_str}"


def call_sarvam_chat(question: str, entries: list[dict[str, Any]]) -> str:
    """
    Call Sarvam-105B (sarvam-105b-conversations) with retrieved archive evidence only.
    Raises RuntimeError on technical/API failure so errors are never confused with no-source fallback.
    """
    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Backend SARVAM_API_KEY is not configured.")

    evidence_text = _build_evidence_context(entries)
    system_prompt = (
        "You are KalaSetu, a strictly source-grounded Indian craft archive assistant.\n"
        "STRICT GROUNDING RULES:\n"
        "1. Answer the learner's question using ONLY the facts explicitly stated in the ARCHIVE EVIDENCE below.\n"
        "2. Do NOT use outside world knowledge, assumptions, or unrecorded facts.\n"
        "3. Do NOT invent artisan names, first-person quotes, or audio recordings. If a source is institutional documentation, cite its Source Title and Organization/Publisher.\n"
        "4. If the ARCHIVE EVIDENCE does not answer the learner's specific question, output ONLY this exact sentence and nothing else:\n"
        f"{NO_SOURCE_FALLBACK}\n"
        "5. In every grounded answer, clearly state the factual details from the archive and cite the supporting source title/organization (or artisan/recording for oral entries) and entry ID."
    )
    user_prompt = (
        f"ARCHIVE EVIDENCE:\n{evidence_text}\n\n"
        f"LEARNER QUESTION: {question}\n\n"
        "Provide a concise, grounded answer with source citation (or the exact fallback if unanswerable from the evidence):"
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
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": 350,
    }

    try:
        response = httpx.post(
            SARVAM_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
    except httpx.RequestError as exc:
        raise RuntimeError(f"Failed to connect to Sarvam-105B API: {exc.__class__.__name__}") from exc

    if response.status_code != 200:
        detail = response.text[:250] if response.text else f"HTTP {response.status_code}"
        raise RuntimeError(f"Sarvam-105B API error ({response.status_code}): {detail}")

    try:
        data = response.json()
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
    except (ValueError, IndexError, AttributeError) as exc:
        raise RuntimeError("Invalid response payload from Sarvam-105B API.") from exc

    if not content or not str(content).strip():
        raise RuntimeError("Sarvam-105B returned an empty message content.")

    return str(content).strip()


def answer_learner_question(
    question: str,
    craft: Optional[str] = None,
    archive_path: Optional[Path] = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Retrieve archive evidence and generate a strictly grounded answer with citations.
    Returns exact fallback 'Mere paas iska source nahi hai.' when no evidence is found.
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    retrieved = search_archive(question, craft=craft, archive_path=archive_path)
    if not retrieved:
        return {
            "question": question,
            "craft": craft,
            "grounded": False,
            "answer": NO_SOURCE_FALLBACK,
            "citations": [],
            "source_links": [],
            "sources": [],
            "model": None,
        }

    if use_llm:
        raw_answer = call_sarvam_chat(question, retrieved)
    else:
        raw_answer = _synthesize_deterministic_grounded_answer(retrieved)

    if NO_SOURCE_FALLBACK.lower() in raw_answer.lower():
        return {
            "question": question,
            "craft": craft,
            "grounded": False,
            "answer": NO_SOURCE_FALLBACK,
            "citations": [],
            "source_links": [],
            "sources": [],
            "model": SARVAM_CHAT_MODEL if use_llm else "deterministic-archive",
        }

    citations = [e["citation"] for e in retrieved]
    citations_footer = " | ".join(citations)
    # Guarantee explicit source citation line in the returned answer text
    if citations_footer not in raw_answer:
        final_answer = f"{raw_answer}\n\nSource: {citations_footer}"
    else:
        final_answer = raw_answer

    source_links = [
        {
            "id": e["id"],
            "source_title": e.get("source_title"),
            "source_organization": e.get("source_organization"),
            "source_url": e.get("source_url"),
        }
        for e in retrieved
        if e.get("source_url")
    ]

    sources = [
        {
            "id": e["id"],
            "record_type": e.get(
                "record_type",
                "institutional_documentation" if e.get("source_title") and not e.get("artisan_name") else "oral_contribution",
            ),
            "verification_status": e.get("verification_status", "verified"),
            "craft": e["craft"],
            "technique": e["technique"],
            "source_title": e.get("source_title"),
            "source_organization": e.get("source_organization"),
            "source_url": e.get("source_url"),
            "supported_facts": e.get("supported_facts", []),
            "excerpt": e.get("excerpt") or e.get("transcript", ""),
            "artisan_name": e.get("artisan_name"),
            "language": e.get("language", "en-IN"),
            "source_audio": e.get("source_audio"),
            "segment": e.get("segment", ""),
            "transcript": e.get("transcript", ""),
            "steps": e.get("steps", []),
            "materials": e.get("materials", []),
            "is_demo": bool(e.get("is_demo", False)),
            "citation": e["citation"],
        }
        for e in retrieved
    ]

    return {
        "question": question,
        "craft": craft,
        "grounded": True,
        "answer": final_answer,
        "citations": citations,
        "source_links": source_links,
        "sources": sources,
        "model": SARVAM_CHAT_MODEL if use_llm else "deterministic-archive",
    }


GROUNDING_TEST_CASES: list[dict[str, Any]] = [
    # 5 Answerable from Verified Institutional Archive Sources
    {
        "id": "TC-01",
        "craft": "Blue Pottery",
        "question": "Why is Jaipur Blue Pottery considered clay-free and what raw materials are mixed to prepare its dough?",
        "expected_answerable": True,
        "expected_entry_id": "src-blue-pottery-dsource-01",
        "expected_source_title": "Blue Pottery of Jaipur — Tools, Raw Materials, and Making Process",
        "expected_organization": "D'source (IDC School of Design, IIT Bombay & NID Digital Learning Initiative)",
        "expected_url": "https://www.dsource.in/resource/blue-pottery-jaipur/making-process",
    },
    {
        "id": "TC-02",
        "craft": "Blue Pottery",
        "question": "How are Plaster of Paris (POP) moulds and wood turning ash used in shaping Blue Pottery vessels?",
        "expected_answerable": True,
        "expected_entry_id": "src-blue-pottery-dsource-01",
        "expected_source_title": "Blue Pottery of Jaipur — Tools, Raw Materials, and Making Process",
        "expected_organization": "D'source (IDC School of Design, IIT Bombay & NID Digital Learning Initiative)",
        "expected_url": "https://www.dsource.in/resource/blue-pottery-jaipur/making-process",
    },
    {
        "id": "TC-03",
        "craft": "Blue Pottery",
        "question": "Which metallic oxides produce the dark blue and turquoise colors on Jaipur Blue Pottery, and how is it glazed and fired?",
        "expected_answerable": True,
        "expected_entry_id": "src-blue-pottery-rajgov-02",
        "expected_source_title": "Blue Pottery of Jaipur — Art and Craft Documentation",
        "expected_organization": "Department of Industries & Commerce, Government of Rajasthan (Handmade in Rajasthan)",
        "expected_url": "https://handmadeinrajasthan.rajasthan.gov.in/content/industries/handmadeinrajasthandepartment/artandcraft/bluepottery/bluepottery-jaipur.html",
    },
    {
        "id": "TC-04",
        "craft": "Paithani Weaving",
        "question": "Why is a Paithani saree reversible with no floating threads on the back, and what is the Bangadi Mor motif?",
        "expected_answerable": True,
        "expected_entry_id": "src-paithani-sahapedia-01",
        "expected_source_title": "Paithani Saree: Woven Histories of Maharashtra",
        "expected_organization": "Sahapedia (Open Online Resource on the Arts and Cultures of India)",
        "expected_url": "https://www.sahapedia.org/paithani-saree-woven-histories-of-maharashtra",
    },
    {
        "id": "TC-05",
        "craft": "Paithani Weaving",
        "question": "How are raw mulberry silk degumming, Kadiyal border interlocking with three shuttles, and tilli bobbins used in Paithani weaving?",
        "expected_answerable": True,
        "expected_entry_id": "src-paithani-craftmark-02",
        "expected_source_title": "Craftmark Process Standards: Paithani Weaving",
        "expected_organization": "All India Artisans and Craftworkers Welfare Association (AIACA) — Craftmark",
        "expected_url": "http://www.craftmark.org/cms/public/uploads/1595673685.pdf",
    },
    # 5 Unanswerable (Not in Archive)
    {
        "id": "TC-06",
        "craft": "Blue Pottery",
        "question": "What is the wholesale export price and GST tax rate for Blue Pottery vases?",
        "expected_answerable": False,
    },
    {
        "id": "TC-07",
        "craft": "Blue Pottery",
        "question": "Which airline cargo carrier offers discounted freight rates for shipping Blue Pottery overseas?",
        "expected_answerable": False,
    },
    {
        "id": "TC-08",
        "craft": "Paithani Weaving",
        "question": "How many watts of electricity does a high-speed automated powerloom consume for polyester sarees?",
        "expected_answerable": False,
    },
    {
        "id": "TC-09",
        "craft": "Paithani Weaving",
        "question": "Which commercial liquid detergent brand is recommended for washing Paithani sarees in a washing machine?",
        "expected_answerable": False,
    },
    {
        "id": "TC-10",
        "craft": "Blue Pottery",
        "question": "How is ivory wood seasoned and polished with lac sticks on a high-speed lathe in Channapatna toy making?",
        "expected_answerable": False,
    },
]


def run_grounding_benchmark(
    use_llm: bool = False,
    archive_path: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Run the 10-question grounding evaluation (5 answerable, 5 unanswerable).
    Pass criteria:
    - Answerable: grounded=True, answer != fallback, and expected entry ID, source_title, organization, and URL are cited.
    - Unanswerable: grounded=False, answer == 'Mere paas iska source nahi hai.', and citations == [].
    """
    results = []
    passed_count = 0

    for tc in GROUNDING_TEST_CASES:
        res = answer_learner_question(
            question=tc["question"],
            craft=tc["craft"],
            archive_path=archive_path,
            use_llm=use_llm,
        )
        if tc["expected_answerable"]:
            cite_blob = " ".join(res["citations"])
            source_ids = [s["id"] for s in res["sources"]]
            source_urls = [s.get("source_url") for s in res["sources"]]
            has_entry = tc["expected_entry_id"] in source_ids and tc["expected_entry_id"] in cite_blob
            has_title = tc["expected_source_title"] in cite_blob and tc["expected_source_title"] in res["answer"]
            has_org = tc["expected_organization"] in cite_blob
            has_url = tc["expected_url"] in source_urls and tc["expected_url"] in cite_blob
            passed = (
                res["grounded"] is True
                and res["answer"] != NO_SOURCE_FALLBACK
                and has_entry
                and has_title
                and has_org
                and has_url
            )
        else:
            passed = (
                res["grounded"] is False
                and res["answer"] == NO_SOURCE_FALLBACK
                and len(res["citations"]) == 0
                and len(res["sources"]) == 0
            )

        if passed:
            passed_count += 1

        results.append({
            "id": tc["id"],
            "craft": tc["craft"],
            "question": tc["question"],
            "expected_answerable": tc["expected_answerable"],
            "grounded": res["grounded"],
            "answer": res["answer"],
            "citations": res["citations"],
            "source_links": res.get("source_links", []),
            "passed": passed,
        })

    total = len(GROUNDING_TEST_CASES)
    return {
        "total": total,
        "passed": passed_count,
        "pass_rate": f"{passed_count}/{total} ({int((passed_count / total) * 100)}%)",
        "pass_criteria": (
            "Answerable (5): Must retrieve matching verified archive entry, generate an answer grounded in the source, "
            "and cite exact source title, publisher/organization, URL, and entry ID. "
            "Unanswerable (5): Must return exact 'Mere paas iska source nahi hai.' with zero fabricated citations."
        ),
        "results": results,
    }
