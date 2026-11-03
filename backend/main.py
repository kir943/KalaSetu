import os
from pathlib import Path
from typing import Any, Optional
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from backend.retrieval import add_oral_entry, format_citation, get_lesson, load_archive
from backend.saaras import transcribe_audio_with_saaras
from backend.qa import answer_learner_question, run_grounding_benchmark
from backend.tts import synthesize_speech_with_bulbul
from backend.mcp_server import invoke_mcp_tool, list_mcp_tools

# Load .env file
env_path = Path(__file__).resolve().parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(
    title="KalaSetu v2 API",
    description="Voice-first artisan archive and craft-learning assistant backend",
    version="2.0.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OralEntryRequest(BaseModel):
    craft: str = Field(..., min_length=1)
    technique: str = Field(..., min_length=1)
    artisan_name: str = Field(..., min_length=1)
    transcript: str = Field(..., min_length=1)
    source_audio: str = Field(..., min_length=1)
    segment: str = Field(..., min_length=1)
    language: str = Field(default="hi-IN")
    steps: Optional[Any] = Field(default_factory=list)
    materials: Optional[Any] = Field(default_factory=list)
    is_demo: bool = Field(default=False)


class LearnerQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1)
    craft: Optional[str] = Field(default=None)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_language_code: str = Field(default="hi-IN")


class MCPToolCallRequest(BaseModel):
    name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/health")
def health_check():
    api_key_set = bool(os.getenv("SARVAM_API_KEY") and len(os.getenv("SARVAM_API_KEY", "").strip()) > 5)
    return {
        "status": "ok",
        "app": "KalaSetu v2",
        "sarvam_configured": api_key_set
    }


@app.get("/api/entries")
def list_entries(craft: Optional[str] = None):
    entries = load_archive()
    if craft and craft.strip():
        c_lower = craft.strip().lower()
        entries = [e for e in entries if e.get("craft", "").strip().lower() == c_lower]
    enriched = []
    for e in entries:
        item = dict(e)
        item["citation"] = format_citation(e)
        enriched.append(item)
    return {"entries": enriched, "count": len(enriched)}


@app.get("/api/lesson")
def fetch_lesson(craft: str, technique: Optional[str] = None):
    return get_lesson(craft=craft, technique=technique)


@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language_code: str = Form("hi-IN"),
):
    file_bytes = await file.read()
    try:
        result = transcribe_audio_with_saaras(
            file_bytes=file_bytes,
            filename=file.filename or "",
            content_type=file.content_type or "audio/wav",
            language_code=language_code,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/entries", status_code=201)
def create_oral_entry(payload: OralEntryRequest):
    try:
        saved = add_oral_entry(payload.model_dump())
        return saved
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ask")
def ask_archive(payload: LearnerQuestionRequest):
    try:
        return answer_learner_question(
            question=payload.question,
            craft=payload.craft,
            use_llm=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/tts")
def text_to_speech(payload: TTSRequest):
    try:
        return synthesize_speech_with_bulbul(
            text=payload.text,
            target_language_code=payload.target_language_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/grounding-test")
def grounding_test(live_llm: bool = False):
    try:
        return run_grounding_benchmark(use_llm=live_llm)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/mcp/tools")
def get_mcp_tools():
    return {"tools": list_mcp_tools()}


@app.post("/api/mcp/call")
def call_mcp_endpoint(payload: MCPToolCallRequest):
    try:
        result = invoke_mcp_tool(payload.name, payload.arguments)
        return {"tool": payload.name, "result": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
