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
        steps_str = "; ".join(entry.get("steps", []))
        materials_str = ", ".join(entry.get("materials", []))
        block = (
            f"[Source {idx}]\n"
            f"Artisan Name: {entry.get('artisan_name')}\n"
            f"Craft: {entry.get('craft')}\n"
            f"Technique: {entry.get('technique')}\n"
            f"Source Recording: {entry.get('source_audio')}\n"
            f"Source Segment: {entry.get('segment')}\n"
            f"Citation: {entry.get('citation')}\n"
            f"Materials: {materials_str}\n"
            f"Steps: {steps_str}\n"
            f"Original Transcript: {entry.get('transcript')}\n"
        )
        blocks.append(block)
    return "\n\n".join(blocks)


def _synthesize_deterministic_grounded_answer(entries: list[dict[str, Any]]) -> str:
    """
    Constructs a strictly archive-backed summary from retrieved entries (used when
    use_llm=False in fast offline unit tests).
    """
    parts = []
    for entry in entries:
        steps_str = " ".join(entry.get("steps", []))
        materials_str = ", ".join(entry.get("materials", []))
        parts.append(
            f"According to {entry['artisan_name']} ({entry['source_audio']}, {entry['segment']}): "
            f"{entry['technique']}. Materials: {materials_str}. Steps: {steps_str} "
            f"Transcript: \"{entry['transcript']}\""
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
        "You are KalaSetu, a voice-first artisan archive assistant.\n"
        "STRICT GROUNDING RULES:\n"
        "1. Answer the learner's question using ONLY the facts explicitly stated in the ARCHIVE EVIDENCE below.\n"
        "2. Do NOT use outside world knowledge, assumptions, or unrecorded facts.\n"
        "3. If the ARCHIVE EVIDENCE does not answer the learner's specific question, output ONLY this exact sentence and nothing else:\n"
        f"{NO_SOURCE_FALLBACK}\n"
        "4. In every grounded answer, clearly state the factual details from the archive and cite the artisan name, recording filename, and segment."
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

    sources = [
        {
            "id": e["id"],
            "craft": e["craft"],
            "technique": e["technique"],
            "artisan_name": e["artisan_name"],
            "language": e["language"],
            "source_audio": e["source_audio"],
            "segment": e["segment"],
            "transcript": e["transcript"],
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
        "sources": sources,
        "model": SARVAM_CHAT_MODEL if use_llm else "deterministic-archive",
    }


GROUNDING_TEST_CASES: list[dict[str, Any]] = [
    # 5 Answerable from Archive
    {
        "id": "TC-01",
        "craft": "Blue Pottery",
        "question": "How many parts of powdered quartz stone, katira gum, and multani mitti are mixed in Blue Pottery?",
        "expected_answerable": True,
        "expected_artisan": "Ramesh Kumar Kumhar (DEMO)",
        "expected_audio": "demo_ramesh_blue_pottery_seg1.wav",
        "expected_segment": "Segment 1",
    },
    {
        "id": "TC-02",
        "craft": "Blue Pottery",
        "question": "Does Jaipur Blue Pottery use regular potter's clay (mitti), and how many hours is the dough kept in a damp cloth?",
        "expected_answerable": True,
        "expected_artisan": "Ramesh Kumar Kumhar (DEMO)",
        "expected_audio": "demo_ramesh_blue_pottery_seg1.wav",
        "expected_segment": "Segment 1",
    },
    {
        "id": "TC-03",
        "craft": "Blue Pottery",
        "question": "At what temperature in degrees Celsius and for how many hours is Blue Pottery fired in the wood kiln (bhatti)?",
        "expected_answerable": True,
        "expected_artisan": "Ramesh Kumar Kumhar (DEMO)",
        "expected_audio": "demo_ramesh_blue_pottery_seg1.wav",
        "expected_segment": "Segment 1",
    },
    {
        "id": "TC-04",
        "craft": "Paithani Weaving",
        "question": "How many wooden shuttles (dhote) are used on the handloom for the Kadiyal interlocking border?",
        "expected_answerable": True,
        "expected_artisan": "Shantabai Kulkarni (DEMO)",
        "expected_audio": "demo_shantabai_paithani_seg2.wav",
        "expected_segment": "Segment 2",
    },
    {
        "id": "TC-05",
        "craft": "Paithani Weaving",
        "question": "How is the Bangadi Mor motif woven on the pallu and what kind of gold-plated silver zari and bamboo spindles (tilli) are used?",
        "expected_answerable": True,
        "expected_artisan": "Shantabai Kulkarni (DEMO)",
        "expected_audio": "demo_shantabai_paithani_seg2.wav",
        "expected_segment": "Segment 2",
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
        "question": "Which king originally invited Blue Pottery artisans from Persia to Jaipur in the 19th century?",
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
    - Answerable: grounded=True, answer != fallback, and expected artisan, source_audio, and segment are cited.
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
            has_artisan = tc["expected_artisan"] in cite_blob and tc["expected_artisan"] in res["answer"]
            has_audio = tc["expected_audio"] in cite_blob and tc["expected_audio"] in res["answer"]
            has_segment = tc["expected_segment"] in cite_blob and tc["expected_segment"] in res["answer"]
            passed = (
                res["grounded"] is True
                and res["answer"] != NO_SOURCE_FALLBACK
                and has_artisan
                and has_audio
                and has_segment
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
            "passed": passed,
        })

    total = len(GROUNDING_TEST_CASES)
    return {
        "total": total,
        "passed": passed_count,
        "pass_rate": f"{passed_count}/{total} ({int((passed_count / total) * 100)}%)",
        "pass_criteria": (
            "Answerable (5): Must retrieve matching archive entry, generate an answer grounded in the source, "
            "and cite exact artisan name, source audio filename, and segment. "
            "Unanswerable (5): Must return exact 'Mere paas iska source nahi hai.' with zero fabricated citations."
        ),
        "results": results,
    }
