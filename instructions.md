You are a senior full-stack AI engineer.

Build a complete working GraphRAG-based AI Orchestrator web application using:

Frontend:
- React (Vite)
- Tailwind CSS
- Zustand (state management)

Backend:
- Python (FastAPI)
- Async background processing (BackgroundTasks, no Celery)
- Local storage (JSON / pickle / FAISS for vectors)
- No external DB (NO Neo4j, NO Postgres, NO Pinecone)
- No Docker

---

# 🎯 APPLICATION GOAL

Build an AI system where user:

1. Uploads files(PDF, DOCX, TXT, CSV, Excel) or connects data
2. System processes data 
   * Cleaning
   * Chunking
   * Entity & Relationship extraction
   * Graph construction
   * Embedding + indexing
into GraphRAG
3. User asks a prompt
4. System:
   - Matches with existing SLM
   - Decides reuse / modify / create new SLM
   - Routes best model
   - Shows reasoning + decision intelligence
5. Executes final run with full trace
6. Provides output + download
7. Learns over time by storing and improving SLMs

---

# 🧩 CORE MODULES

Implement these modules:

1. Data Ingestion
2. Processing Pipeline
3. GraphRAG Engine (local graph)
4. Vector Search (FAISS)
5. SLM Registry (persistent JSON storage)
6. Model Router
7. Decision Engine
8. Execution Trace Engine

---

# 📊 STEP 1: DASHBOARD PAGE

Create Dashboard UI:

Top Cards:
- Tokens Saved This Month
- Total Active SLMs
- Files Ingested
- Total Cost Saved

Second Section:
- Recent Sessions (list)

Actions:
- Upload File
- Connect Data Source (mock only)
- Scrape URL (simple fetch)

---

# 📤 STEP 2: DATA INGESTION

Frontend:
- Drag & drop file upload
- Show uploaded files list

Backend APIs:

POST /upload
- Save file to /data/files/

POST /scrape
- Fetch URL text (basic)

Supported:
- PDF (PyPDF)
- DOCX
- TXT
- CSV / XLSX

---

# ⚙️ STEP 3: PROCESSING PIPELINE

For each file:

Pipeline Steps:

1. Extract text
2. Clean text
3. Chunk (200–500 tokens)
4. Entity extraction (spaCy or fallback)
5. Relationship extraction
6. Build graph (store JSON)
7. Generate embeddings
8. Store in FAISS index

Store:
/data/processed/{file_id}.json

---

# 📊 STEP 4: STATUS TRACKING

Track per file:

- uploaded
- processing
- cleaned
- chunked
- entities_extracted
- graph_built
- indexed
- completed
- failed

Frontend:
- Table + progress bar
- Auto polling (2 sec)

API:
GET /status

---

# 🧠 STEP 5: GRAPHRAG QUERY ENGINE

API:
POST /query

Pipeline:

1. Embed query
2. Extract entities
3. Retrieve:
   - Top-K chunks (FAISS)
   - Graph neighbors (JSON traversal)
4. Merge context
5. Call LLM
6. Return:

{
  answer,
  sources,
  graph_relations
}

---

# 🧠 STEP 6: SLM REGISTRY (PERSISTENT MEMORY)

Store in:
/data/slm_registry.json

Each SLM:

{
  id,
  name,
  embedding_vector,
  parameters,
  age,
  usage_count,
  created_at,
  last_used
}

IMPORTANT:
- This file MUST persist across sessions
- Load on server start
- Update after every query

---

# ⚙️ STEP 7: SLM MATCHING LOGIC

When user clicks "Analyse":

1. Convert prompt → embedding
2. Compare with all SLM embeddings (cosine similarity)

Decision Rules:

IF score > 0.80:
    → Use existing SLM
    → Increment usage_count
    → Update last_used

IF 0.50 – 0.79:
    → Use existing SLM with modification
    → Update parameters slightly
    → Save updated SLM back to registry

IF < 0.50:
    → CREATE NEW SLM

    New SLM must include:
    - New ID
    - Prompt embedding
    - Initial parameters
    - usage_count = 1
    - created_at timestamp

    🚨 CRITICAL REQUIREMENT:
    - Newly created SLM MUST be saved to /data/slm_registry.json
    - It MUST be available for future matching
    - Registry file must be updated immediately

Return:

- selected SLM
- match score
- decision type

---

# 📊 STEP 8: SLM RESULT CARDS

Show:

- SLM Name
- Match Score
- Parameters
- Tokens Saved
- Age

---

# 🤖 STEP 9: MODEL ROUTING

Models (mock):

- GPT-4
- Claude
- Gemini
- Local LLM
- Fast Model

Score based on:

- Prompt complexity
- Context size
- Estimated cost

Return top 4–5 ranked models.

---

# 🧠 STEP 10: INTELLIGENCE CONNECTION MAP

Graph Nodes:

- Files
- Entities
- SLM
- Prompt

Edges:

- derived_from
- related_to
- used_by

Frontend:
- react-force-graph visualization

---

# 📊 STEP 11: DECISION CARDS

Show:

- Task Complexity
- SLM Confidence
- Estimated Cost

---

# ▶️ STEP 12: FINAL RUN

On click:

1. Execute GraphRAG pipeline
2. Use selected SLM
3. Use selected model
4. Generate final output

Track:

- Tokens used
- Execution time
- Steps

---

# 📜 STEP 13: PROCESS TRACE

Timeline view:

- Query received
- SLM matched / created
- Retrieval completed
- Model selected
- LLM response generated

---

# 📊 STEP 14: SESSION INSIGHTS

Show:

- Tokens used
- Tokens saved (via SLM reuse)
- Cost estimate
- Execution time
- SLM used

---

# 📥 STEP 15: OUTPUT

Allow:

- Download (TXT/JSON)
- If project request → generate structured output

---

# 📁 BACKEND STRUCTURE

/backend
  main.py
  ingestion.py
  processing.py
  entity_extraction.py
  graph_builder.py
  embedding.py
  slm.py
  router.py
  decision.py
  trace.py

---

# 📁 FRONTEND STRUCTURE

/src
  /components
    Dashboard.jsx
    Upload.jsx
    FileTable.jsx
    GraphView.jsx
    ChatUI.jsx
    SLMPanel.jsx
    ModelRouter.jsx
    DecisionCards.jsx
    TraceView.jsx

  /store
  /services

---

# ⚡ RULES

- No external DB
- Use JSON persistence
- Use FAISS for vectors
- Modular architecture
- Async processing
- Proper logging + error handling

---

# 🎨 UI FLOW

1. Dashboard
2. Upload & Process
3. Analyse Prompt & SLM Decision
4. Model Routing
5. Intelligence Map
6. Decision Cards
7. Final Run
8. Trace + Output

---

# 🧪 BONUS

- Sample dataset
- Basic auth (optional)

---

# 📦 OUTPUT REQUIREMENTS

Generate:

1. Full backend (FastAPI)
2. Full frontend (React)
3. Setup steps
4. .env example
5. README

Write real working code.
Do NOT skip logic.
Ensure SLM persistence works correctly.
