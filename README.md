# KalaSetu v2 — Every Answer Has a Source

> **“AI jo craft ke baare mein kuch bhi bol deta hai, woh preservation nahi hai. KalaSetu sirf wahi bolta hai jo kisi artisan ne record kiya hai, aur har jawab ke saath source dikhata hai.”**

---

## 1. Project Overview & Problem Statement

Generic large language models frequently hallucinate craft techniques, ratios, temperatures, and regional weaving methods when asked about traditional Indian crafts. Presenting unverified AI guesses as cultural knowledge undermines authentic craft preservation.

**KalaSetu v2** is a voice-first artisan archive and grounded craft-learning assistant designed to solve this problem:
- **Artisans contribute oral knowledge** in Hindi (`hi-IN`) or Marathi (`mr-IN`) by uploading voice recordings.
- **Human-in-the-loop review**: Recordings are transcribed via **Sarvam Saaras** (`saaras:v3`), and the artisan reviews and edits the transcript, technique title, steps, and materials before saving to the archive.
- **Strictly grounded learner Q&A**: When a learner asks a question, KalaSetu retrieves matching entries from the archive and uses **Sarvam-105B** (`sarvam-105b-conversations`) strictly on the retrieved evidence. Every answer cites the exact **artisan name**, **source recording file**, and **segment**.
- **Zero-guess refusal**: If the archive does not contain evidence for a question, KalaSetu refuses to guess and returns the exact sentence:
  **`Mere paas iska source nahi hai.`**
- **Spoken answers**: Learners can click **Listen (Speak Answer)** on any grounded answer to hear it spoken aloud via **Sarvam Bulbul** (`bulbul:v3`).

---

## 2. Features Implemented

1. **Artisan Audio Contribution (`POST /api/transcribe` & `POST /api/entries`)**:
   - Supports `.wav`, `.mp3`, `.ogg`, `.m4a`, `.flac`, `.aac`, and `.webm` uploads (up to 15 MB; synchronous REST clips up to 30 seconds).
   - Calls `https://api.sarvam.ai/speech-to-text` (`model="saaras:v3"`, `mode="transcribe"`, `with_timestamps="true"`).
   - **Honest timestamp & chunk handling**: When Saaras returns word-level `start_time_seconds` and `end_time_seconds`, KalaSetu formats the exact time range (`Segment 1 (<start>s - <end>s)`). When word timestamps are empty or not returned, it records an explicit chunk-level source (`Chunk 1 (Full uploaded audio clip — timestamps not returned by Saaras)`) and never fabricates timestamps.
2. **Reviewed Transcript & Structured Local Archive (`backend/data/archive.json`)**:
   - Stores each entry with `id`, `craft`, `technique`, `steps`, `materials`, `artisan_name`, `language`, `source_audio`, `segment`, `transcript`, `created_at`, and `is_demo`.
3. **Grounded Learner Q&A with Citations (`POST /api/ask`)**:
   - Lexical/keyword retrieval (`search_archive`) with stopword removal, suffix stem normalization, and generic craft-title filtering to prevent false positives on unrecorded topics.
   - Calls `https://api.sarvam.ai/v1/chat/completions` (`model="sarvam-105b-conversations"`, `temperature=0.0`) using only retrieved archive evidence.
   - Displays the grounded answer, verified citation(s), and an inspectable card showing the original retrieved artisan transcript.
   - Keeps technical upstream API failures (`HTTP 502`) completely distinct from the no-source fallback (`Mere paas iska source nahi hai.`).
4. **Spoken Answers with Sarvam Bulbul (`POST /api/tts`)**:
   - Calls `https://api.sarvam.ai/text-to-speech` (`model="bulbul:v3"`, `speaker="shubh"`) for grounded answers in `hi-IN`, `mr-IN`, or `en-IN`.
   - Plays returned audio directly in the browser `<audio>` element and falls back cleanly to text if TTS fails.
   - Explicitly refuses to synthesize speech for the no-source fallback (`Mere paas iska source nahi hai.`).
5. **Minimal MCP Server (`backend/mcp_server.py`)**:
   - Exposes `search_archive`, `add_oral_entry`, and `get_lesson` over JSON-RPC 2.0 (`stdio` and `/api/mcp/*`) by directly wrapping `backend/retrieval.py` without duplicating business logic.

---

## 3. Tech Stack & Architecture

- **Frontend**: React 18, Vite 6, plain CSS (`frontend/`)
- **Backend**: Python 3.12, FastAPI, Uvicorn, HTTPX, Pydantic (`backend/`)
- **Storage**: Local JSON file (`backend/data/archive.json`) — no external database required
- **Retrieval**: Deterministic keyword matching with suffix normalization and coverage thresholds (`backend/retrieval.py`)
- **Sarvam AI Integrations** (all called strictly from the FastAPI backend):
  - **Speech-to-Text**: Sarvam Saaras (`saaras:v3` at `https://api.sarvam.ai/speech-to-text`)
  - **Grounded Generation**: Sarvam-105B (`sarvam-105b-conversations` at `https://api.sarvam.ai/v1/chat/completions`)
  - **Text-to-Speech**: Sarvam Bulbul (`bulbul:v3` at `https://api.sarvam.ai/text-to-speech`)
- **MCP**: JSON-RPC 2.0 server (`backend/mcp_server.py`)

```text
[React + Vite Frontend (Port 5173)]
        │  (/api proxy)
        ▼
[FastAPI Backend (Port 8000)] ──► [backend/data/archive.json]
        ├──► POST /api/transcribe ──► Sarvam Saaras STT (saaras:v3)
        ├──► POST /api/ask        ──► Retrieval Gate + Sarvam-105B (sarvam-105b-conversations)
        ├──► POST /api/tts        ──► Sarvam Bulbul TTS (bulbul:v3)
        └──► MCP Server           ──► search_archive | add_oral_entry | get_lesson
```

---

## 4. Project Structure

```text
KalaSetu/
├── .env.example                 # Root placeholder environment template
├── .gitignore                   # Git ignore rules protecting .env, venvs, caches, dist
├── README.md                    # Project documentation, test catalog, and demo guide
├── backend/
│   ├── .env.example             # Backend placeholder environment template (SARVAM_API_KEY=your_key_here)
│   ├── main.py                  # FastAPI application and HTTP routes
│   ├── retrieval.py             # Archive loader, search_archive, get_lesson, add_oral_entry
│   ├── saaras.py                # Sarvam Saaras speech-to-text client and upload validation
│   ├── qa.py                    # Grounded Q&A pipeline, Sarvam-105B client, and 10-question benchmark
│   ├── tts.py                   # Sarvam Bulbul text-to-speech client and fallback refusal guard
│   ├── mcp_server.py            # Minimal MCP server wrapping search_archive, add_oral_entry, get_lesson
│   ├── requirements.txt         # Backend Python dependencies
│   ├── data/
│   │   └── archive.json         # Local JSON archive (seeded with 2 clearly labeled DEMO entries)
│   └── tests/
│       ├── test_health.py       # Block 1 health endpoint and key-leak guard test
│       ├── test_retrieval.py    # Block 2 archive schema, search_archive, and get_lesson tests
│       ├── test_contribution.py # Block 3 upload validation, Saaras error/timestamp handling, and persistence tests
│       ├── test_qa.py           # Block 4 grounded Q&A, citation, no-source fallback, 502 error, and 10-question suite tests
│       ├── test_tts.py          # Block 5 Bulbul TTS generation, no-source refusal, and upstream failure tests
│       └── test_mcp_and_e2e.py  # Block 6 independent MCP tool tests and full end-to-end demo flow test
└── frontend/
    ├── index.html               # HTML entry point
    ├── package.json             # Frontend scripts and dependencies
    ├── vite.config.js           # Vite dev server and /api proxy to FastAPI (127.0.0.1:8000)
    └── src/
        ├── main.jsx             # React root mount
        ├── App.jsx              # Main UI (Ask the Archive, 10-Question Suite, Record Artisan Knowledge)
        └── index.css            # Accessible styling
```

---

## 5. Prerequisites & Local Setup

### Prerequisites
- **Python**: `3.10+` (tested on Python `3.12.10`)
- **Node.js & npm**: Node `18+` / `22+` (tested on Node `v22.17.1`, npm `10.9.2`)
- **Sarvam AI API Subscription Key**

### Step 1: Configure Environment Variables
Copy `backend/.env.example` to `backend/.env` and insert your real Sarvam API key:
```powershell
Copy-Item backend\.env.example backend\.env
```
Edit `backend/.env`:
```env
SARVAM_API_KEY=your_key_here
PORT=8000
HOST=0.0.0.0
```
*Security Note*: `backend/.env` and all `.env` files are ignored by Git. The API key is read exclusively by the Python backend and is never sent to or exposed in the React frontend.

### Step 2: Install & Run the Backend
```powershell
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Verify the backend health check at `http://127.0.0.1:8000/api/health`.

### Step 3: Install & Run the Frontend
In a second terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 6. Running Tests & Production Build

### Run the Full Backend Test Suite (`pytest`)
From the repository root:
```powershell
python -m pytest backend/tests/ -v
```

### Run the Frontend Production Build
```powershell
cd frontend
npm run build
```

---

## 7. Complete Catalog of Tests Performed

All **18 automated backend tests** and the **10-question grounding benchmark** were executed and verified (`18 passed in 0.37s`):

### A. Unit & Integration Test Suite (`backend/tests/`)
1. **`test_health.py::test_health_endpoint`** (Block 1):
   - Verifies `GET /api/health` returns `200 OK`, `{"status": "ok", "app": "KalaSetu v2", "sarvam_configured": ...}`, and never leaks any `sk_` API key string.
2. **`test_retrieval.py::test_archive_has_two_labeled_demo_entries`** (Block 2):
   - Verifies `backend/data/archive.json` contains two seeded crafts (`Blue Pottery` and `Paithani Weaving`) explicitly marked with `"is_demo": true` and `(DEMO)` in `artisan_name`.
3. **`test_retrieval.py::test_known_query_returns_expected_entry_and_citation`** (Block 2):
   - Verifies known craft queries retrieve the expected entry along with formatted source citations (`artisan_name`, `source_audio`, `segment`, and `id`).
4. **`test_retrieval.py::test_unrelated_query_returns_no_evidence`** (Block 2):
   - Verifies both unrelated crafts (Channapatna toys) and unrecorded questions within a known craft (online export price and GST for Blue Pottery) return `[]`.
5. **`test_retrieval.py::test_get_lesson_includes_citations_and_does_not_invent_details`** (Block 2):
   - Verifies `get_lesson` preserves exact archived `steps`, `materials`, `transcript`, and `citations` without inventing missing details, and returns `"Mere paas iska source nahi hai."` when a requested technique does not exist.
6. **`test_contribution.py::test_invalid_audio_upload_rejected`** (Block 3):
   - Verifies `POST /api/transcribe` rejects unsupported file extensions (`.txt`), empty audio files (`0 bytes`), and unsupported language codes (`fr-FR`) with `HTTP 400`.
7. **`test_contribution.py::test_transcription_error_handling`** (Block 3):
   - Verifies upstream Sarvam Saaras failures (`HTTP 503`) return `HTTP 502` with a clear error message and never expose the API key.
8. **`test_contribution.py::test_transcription_success_with_and_without_timestamps`** (Block 3):
   - Verifies that when Saaras returns word-level timestamps, the exact range (`Segment 1 (0.2s - 3.4s)`) is recorded; when timestamps are empty, the explicit chunk label (`Chunk 1 (Full uploaded audio clip — timestamps not returned by Saaras)`) is used without inventing timestamps.
9. **`test_contribution.py::test_save_reviewed_entry_and_persistence`** (Block 3):
   - Verifies saving a reviewed artisan contribution via `add_oral_entry` and `POST /api/entries` persists to JSON and is immediately searchable with citations.
10. **`test_qa.py::test_grounded_answer_and_citation_presence`** (Block 4):
    - Verifies `POST /api/ask` generates an answer strictly from retrieved evidence and includes the source artisan, recording filename, and segment in both `citations` and `answer`.
11. **`test_qa.py::test_no_source_fallback_when_no_evidence`** (Block 4):
    - Verifies unanswerable questions return `grounded: false`, `citations: []`, and the exact string `"Mere paas iska source nahi hai."`.
12. **`test_qa.py::test_api_failure_kept_distinct_from_no_source_fallback`** (Block 4):
    - Verifies upstream Sarvam-105B errors (`HTTP 500`) return `HTTP 502` and are never disguised as `"Mere paas iska source nahi hai."`.
13. **`test_qa.py::test_ten_question_grounding_suite_passes_100_percent`** (Block 4):
    - Runs the 10-question grounding evaluation suite (5 answerable, 5 unanswerable) and asserts a `10/10 (100%)` pass rate.
14. **`test_tts.py::test_tts_successful_audio_generation`** (Block 5):
    - Verifies `POST /api/tts` calls `https://api.sarvam.ai/text-to-speech` (`model="bulbul:v3"`, `speaker="shubh"`) and returns base64 WAV audio.
15. **`test_tts.py::test_tts_refuses_no_source_fallback`** (Block 5):
    - Verifies `POST /api/tts` rejects `"Mere paas iska source nahi hai."` with `HTTP 400` without calling the upstream TTS API.
16. **`test_tts.py::test_tts_upstream_api_failure`** (Block 5):
    - Verifies upstream Bulbul TTS failures return `HTTP 502` cleanly without leaking secrets.
17. **`test_mcp_and_e2e.py::test_mcp_tools_independently`** (Block 6):
    - Independently tests `tools/list` and `tools/call` for all three MCP tools (`search_archive`, `add_oral_entry`, `get_lesson`) via JSON-RPC 2.0.
18. **`test_mcp_and_e2e.py::test_complete_end_to_end_demo_flow`** (Block 6):
    - Verifies the full workflow end-to-end: audio upload & Saaras transcription -> saving reviewed entry -> asking an answerable question with verified citation -> asking an unanswerable question with exact no-source fallback -> synthesizing speech via Bulbul TTS.

### B. 10-Question Grounding Verification Benchmark (`10/10 — 100% Pass Rate`)
| ID | Craft | Question | Category | Expected Outcome | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `TC-01` | Blue Pottery | How many parts of powdered quartz stone, katira gum, and multani mitti are mixed in Blue Pottery? | Answerable | Grounded + Cites `Ramesh Kumar Kumhar (DEMO)`, `demo_ramesh_blue_pottery_seg1.wav`, `Segment 1` | **PASS** |
| `TC-02` | Blue Pottery | Does Jaipur Blue Pottery use regular potter's clay (mitti), and how many hours is the dough kept in a damp cloth? | Answerable | Grounded + Cites `Ramesh Kumar Kumhar (DEMO)`, `demo_ramesh_blue_pottery_seg1.wav`, `Segment 1` | **PASS** |
| `TC-03` | Blue Pottery | At what temperature in degrees Celsius and for how many hours is Blue Pottery fired in the wood kiln (bhatti)? | Answerable | Grounded + Cites `Ramesh Kumar Kumhar (DEMO)`, `demo_ramesh_blue_pottery_seg1.wav`, `Segment 1` | **PASS** |
| `TC-04` | Paithani Weaving | How many wooden shuttles (dhote) are used on the handloom for the Kadiyal interlocking border? | Answerable | Grounded + Cites `Shantabai Kulkarni (DEMO)`, `demo_shantabai_paithani_seg2.wav`, `Segment 2` | **PASS** |
| `TC-05` | Paithani Weaving | How is the Bangadi Mor motif woven on the pallu and what kind of gold-plated silver zari and bamboo spindles (tilli) are used? | Answerable | Grounded + Cites `Shantabai Kulkarni (DEMO)`, `demo_shantabai_paithani_seg2.wav`, `Segment 2` | **PASS** |
| `TC-06` | Blue Pottery | What is the wholesale export price and GST tax rate for Blue Pottery vases? | Unanswerable | Exact `"Mere paas iska source nahi hai."` + `citations: []` | **PASS** |
| `TC-07` | Blue Pottery | Which king originally invited Blue Pottery artisans from Persia to Jaipur in the 19th century? | Unanswerable | Exact `"Mere paas iska source nahi hai."` + `citations: []` | **PASS** |
| `TC-08` | Paithani Weaving | How many watts of electricity does a high-speed automated powerloom consume for polyester sarees? | Unanswerable | Exact `"Mere paas iska source nahi hai."` + `citations: []` | **PASS** |
| `TC-09` | Paithani Weaving | Which commercial liquid detergent brand is recommended for washing Paithani sarees in a washing machine? | Unanswerable | Exact `"Mere paas iska source nahi hai."` + `citations: []` | **PASS** |
| `TC-10` | Blue Pottery | How is ivory wood seasoned and polished with lac sticks on a high-speed lathe in Channapatna toy making? | Unanswerable | Exact `"Mere paas iska source nahi hai."` + `citations: []` | **PASS** |

### C. Live API Contract Smoke Tests Performed
- **Sarvam Saaras STT (`POST https://api.sarvam.ai/speech-to-text`, `saaras:v3`)**: Verified `200 OK` live audio upload and JSON response structure.
- **Sarvam-105B Chat (`POST https://api.sarvam.ai/v1/chat/completions`, `sarvam-105b-conversations`)**: Verified `200 OK` live grounded Q&A with citation and no-source fallback.
- **Sarvam Bulbul TTS (`POST https://api.sarvam.ai/text-to-speech`, `bulbul:v3`)**: Verified `200 OK` live synthesis returning base64 WAV audio.

---

## 8. Demo Flow & Sample Data Notice

### Demo Notice on Seeded Entries
> **Important**: The two initial archive entries in `backend/data/archive.json` (`demo-blue-pottery-01` attributed to *Ramesh Kumar Kumhar (DEMO)* and `demo-paithani-01` attributed to *Shantabai Kulkarni (DEMO)*) are **seeded demonstration entries** created to showcase the MVP retrieval and grounding workflow. They are explicitly marked with `"is_demo": true`, `(DEMO)` in the artisan name, and a `DEMO DATA` badge in the UI, and do not represent field-verified recordings from real individuals. New recordings uploaded and reviewed through the app are marked as `ARTISAN CONTRIBUTION`.

### Step-by-Step Demo Flow
1. **Ask an Answerable Question**:
   - Open the **Ask the Archive (Learner Q&A)** tab.
   - Click the sample chip **“Answerable: Blue Pottery Quartz Ratio”** and click **Ask the Archive**.
   - Inspect the grounded answer, the verified citation (`Ramesh Kumar Kumhar (DEMO) — demo_ramesh_blue_pottery_seg1.wav, Segment 1 (00:00 - 01:15)`), and the original transcript card below.
2. **Listen to the Spoken Answer**:
   - Select a voice language (`hi-IN`, `mr-IN`, or `en-IN`) and click **Listen (Speak Answer)** to play the audio generated by Sarvam Bulbul.
3. **Ask an Unanswerable Question**:
   - Click the sample chip **“Unanswerable: Export Price & GST”** and click **Ask the Archive**.
   - Verify the response is **`Mere paas iska source nahi hai.`** with zero citations and no Listen button.
4. **Contribute New Artisan Knowledge**:
   - Switch to the **Record Artisan Knowledge** tab.
   - Upload a `.wav` or `.mp3` audio clip and click **1. Transcribe Audio with Saaras**.
   - Review/edit the transcript, fill in the Artisan Name, Craft, Technique, Steps, and Materials, and click **2. Save Reviewed Entry to Archive**.
   - Return to **Ask the Archive** and query the newly added technique to see it retrieved and cited.

---

## 9. Current Limitations
- **Synchronous STT clip duration**: The synchronous Sarvam Saaras REST endpoint (`https://api.sarvam.ai/speech-to-text`) supports audio clips up to 30 seconds per upload.
- **Keyword retrieval**: Uses deterministic lexical matching and suffix stem normalization rather than vector embeddings, so learner questions should share at least one specific domain term (in English, Hindi, or Marathi) with the archived entry.
- **Local JSON storage**: Designed for single-instance hackathon MVP use (`backend/data/archive.json`) without concurrent multi-writer database locking.
