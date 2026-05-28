# AI Orchestrator — SLM Intelligence Platform

A full-stack GraphRAG-based AI Orchestrator that learns over time via a persistent SLM (Small Language Model) registry.

## Architecture

```
Data Upload → Processing Pipeline → GraphRAG Engine → SLM Matching → Model Routing → LLM Response
```

### Key features
- **Two entry modes on Inject** — **Role-Based** (pick Legal / Risk / Finance / Data Sci / Product / Custom, answer 2 questions, get role-tailored doc-type suggestions) or **Direct Upload** (Files / Folder / Web URL / Database). Both modes tag uploads with role + domain and converge on the same preprocessing & GraphRAG pipeline.
- **GraphRAG** — entity extraction, knowledge graph, FAISS vector search
- **SLM Registry** — persistent JSON storage; reuse (>80%), modify (50–79%), create (<50%)
- **Model Router** — ranks Claude, GPT-4, Gemini by suitability and cost
- **Full Trace** — every step timed and displayed in the UI
- **No database** — JSON files + FAISS only

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Download spaCy model (for entity extraction)
python -m spacy download en_core_web_sm

# Configure API keys
copy .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY or OPENAI_API_KEY
```

### 2. Frontend

```bash
cd frontend
npm install
```

---

## Running

### Recommended startup (from repo root)
```bash
./start_backend.sh
./start_frontend.sh
```

This uses stable local ports to avoid collisions:
- Backend: `http://127.0.0.1:8010`
- Frontend: `http://127.0.0.1:5180`

### Backend (manual, from /backend directory)
```bash
uvicorn --app-dir $(pwd) main:app --reload --reload-exclude "data/*" --reload-exclude "__pycache__/*" --host 0.0.0.0 --port 8010
```

### Frontend (manual, from /frontend directory)
```bash
npm run dev
```

Open [http://localhost:5180](http://localhost:5180)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Upload file (PDF, DOCX, TXT, CSV, XLSX). Optional `role` & `domain` form fields tag the file for role-aware retrieval. |
| GET | `/status` | Get all file processing statuses |
| GET | `/status/{file_id}` | Get single file status |
| POST | `/scrape` | Scrape URL and ingest text. Optional `role` & `domain` in JSON body. |
| POST | `/analyse` | Match prompt against SLM registry |
| POST | `/query` | GraphRAG query with answer |
| GET | `/graph` | Get knowledge graph data |
| GET | `/graph-canonical` | Get canonical merged graph (suppressed edges excluded) |
| GET | `/wiki/pages` | List generated nano-wiki pages |
| GET | `/wiki/page/{canonical_id}` | Get one nano-wiki page with citations |
| GET | `/wiki/reviews` | List pending/reviewed merge decisions |
| POST | `/wiki/review/{review_id}` | Approve/reject a merge review |
| POST | `/final-run` | Execute full pipeline with trace |
| GET | `/stats` | Dashboard statistics |
| GET | `/quality/metrics` | Quality snapshot: ingestion, registry, graph, wiki citation coverage |
| POST | `/repair/reprocess/{file_id}` | Re-run full processing pipeline for a specific source |
| POST | `/repair/suppress-relation` | Suppress a canonical relation by `edge_key` |
| POST | `/repair/restore-relation` | Restore a previously suppressed canonical relation |
| POST | `/repair/split-entity` | Create a new canonical entity from an alias (wrong-merge repair) |

---

## SLM Decision Logic

```
Cosine similarity (prompt embedding vs SLM embeddings):

score >= 80  → Reuse existing SLM (update usage_count + last_used)
score 50–79  → Modify SLM (blend embeddings 70/30, save updated registry)
score < 50   → Create new SLM (new UUID, save to slm_registry.json immediately)
```

The `data/slm_registry.json` file persists across all sessions. Delete it to reset.

---

## File Structure

```
AI-Orchestrator/
├── backend/
│   ├── main.py              # FastAPI app + all endpoints
│   ├── ingestion.py         # PDF/DOCX/CSV/XLSX/TXT text extraction
│   ├── processing.py        # Pipeline: clean → chunk → extract → graph → index
│   ├── entity_extraction.py # spaCy NER with regex fallback
│   ├── graph_builder.py     # JSON knowledge graph
│   ├── embedding.py         # sentence-transformers + FAISS
│   ├── slm.py               # SLM registry + matching logic
│   ├── router.py            # Model ranking
│   ├── decision.py          # Decision analysis
│   ├── trace.py             # Execution trace engine
│   ├── llm_client.py        # Anthropic/OpenAI/mock LLM calls
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/           # DashboardPage, InjectPage, PromptPage, ModelPage, ResultsPage
│       ├── components/      # Topbar
│       ├── store/           # Zustand global state
│       └── services/        # API client
├── data/
│   ├── slm_registry.json    # Persistent SLM store
│   ├── files/               # Raw uploaded files
│   ├── processed/           # Pipeline status + extracted data
│   ├── graphs/              # Per-file knowledge graphs
│   └── faiss/               # FAISS index + chunk metadata
└── README.md
```

---

## Notes

- On first run, `sentence-transformers` will download `all-MiniLM-L6-v2` (~90MB)
- Without API keys, the system returns structured mock responses but all pipeline stages (ingestion, GraphRAG, SLM matching) run fully
- The SLM registry grows with each unique query type — reset by clearing `data/slm_registry.json`
