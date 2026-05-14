# AGENTS.md

## Purpose
This file gives AI coding agents the minimum repo-specific context needed to work safely and quickly in this codebase.

For product-level requirements and detailed architecture narrative, see:
- [README.md](README.md)
- [instructions.md](instructions.md)

## Working Directories
- Backend commands should be run from `backend/`.
- Frontend commands should be run from `frontend/`.

This matters because backend modules use local imports and relative data paths.

## Setup And Run
### Backend
1. `cd backend`
2. `python -m venv venv`
3. `venv\\Scripts\\activate` (Windows)
4. `pip install -r requirements.txt`
5. `python -m spacy download en_core_web_sm`
6. `copy .env.example .env`
7. Run API: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

### Frontend
1. `cd frontend`
2. `npm install`
3. `npm run dev`

Other frontend scripts:
- `npm run build`
- `npm run preview`

## Validation Expectations
- There is no established backend test suite in this repo.
- There are no frontend `test` or `lint` scripts currently defined.
- For changes, prefer targeted validation:
  - Backend: start API from `backend/` and hit the affected endpoint(s).
  - Frontend: run the dev server and verify the affected flow in UI.
  - Build-only frontend changes can be checked with `npm run build` from `frontend/`.

## High-Value File Map
### Backend
- API entry and endpoint orchestration: [backend/main.py](backend/main.py)
- Processing pipeline and status lifecycle: [backend/processing.py](backend/processing.py)
- Embeddings and FAISS persistence: [backend/embedding.py](backend/embedding.py)
- Entity and relationship extraction: [backend/entity_extraction.py](backend/entity_extraction.py)
- Graph creation/query: [backend/graph_builder.py](backend/graph_builder.py)
- SLM registry and similarity decisions: [backend/slm.py](backend/slm.py)
- Model ranking logic: [backend/router.py](backend/router.py)
- Decision analytics summary: [backend/decision.py](backend/decision.py)
- LLM provider client and fallback behavior: [backend/llm_client.py](backend/llm_client.py)
- Trace instrumentation: [backend/trace.py](backend/trace.py)

### Frontend
- App step flow shell: [frontend/src/App.jsx](frontend/src/App.jsx)
- Global state and actions: [frontend/src/store/index.js](frontend/src/store/index.js)
- API client and endpoint contracts: [frontend/src/services/api.js](frontend/src/services/api.js)
- Step pages: [frontend/src/pages](frontend/src/pages)
- Shared top navigation: [frontend/src/components/Topbar.jsx](frontend/src/components/Topbar.jsx)
- Styling and theme utilities: [frontend/src/index.css](frontend/src/index.css)

## Repo-Specific Conventions
- Keep backend endpoint handlers thin; place logic in module-level services.
- Persist artifacts locally (JSON/FAISS) under `data/` and `backend/data/` patterns already used by modules.
- Preserve the local-only architecture in [instructions.md](instructions.md): no external DB, vector DB, or graph DB unless the user explicitly asks for that change.
- Preserve SLM decision thresholds and persistence behavior in [backend/slm.py](backend/slm.py).
- Route frontend network calls through [frontend/src/services/api.js](frontend/src/services/api.js) and keep state transitions in [frontend/src/store/index.js](frontend/src/store/index.js).

## Common Pitfalls
- Running backend from the wrong working directory can break local imports and store artifacts in unexpected locations.
- Frontend API configuration can drift: [frontend/src/services/api.js](frontend/src/services/api.js) calls `VITE_API_URL` or `http://localhost:8000` directly, while [frontend/vite.config.js](frontend/vite.config.js) only proxies `/api` requests.
- Missing API keys are allowed, but backend returns mock LLM outputs; check [backend/.env.example](backend/.env.example) before debugging provider behavior.
- First run may download models (sentence-transformers/spaCy), which can look like startup slowness.
- Searches can be noisy because `backend/venv/` is checked into the workspace; scope searches to `backend/*.py`, `frontend/src/**`, or similar paths when possible.

## Change Strategy For Agents
1. Identify affected boundary first (API orchestration, pipeline, retrieval, routing, or UI step page).
2. Make the smallest change in the most local module.
3. Validate the exact user flow or endpoint touched.
4. Avoid broad refactors unless explicitly requested.
