---
description: "Use when working in backend Python modules, FastAPI endpoints, the processing pipeline, GraphRAG retrieval, SLM registry logic, or local persistence."
applyTo: "backend/**/*.py"
---

# Backend Working Rules

- Run backend commands from `backend/`; local imports and `data/...` paths depend on that working directory.
- Keep [backend/main.py](../backend/main.py) handlers thin. Put behavior in the owning module such as [backend/processing.py](../backend/processing.py), [backend/slm.py](../backend/slm.py), or [backend/embedding.py](../backend/embedding.py).
- Preserve the local persistence model: JSON artifacts, graph files, and FAISS indexes under the existing `data/` paths. Do not introduce external databases or hosted vector stores unless explicitly requested.
- Treat fallback behavior as intentional before debugging it away: embeddings can fall back locally, and LLM responses can be mocked when provider keys are missing.
- Preserve SLM registry thresholds and immediate persistence semantics in [backend/slm.py](../backend/slm.py).
- Validate backend changes by starting the API from `backend/` and exercising the affected endpoint or flow. There is no established backend test suite in this repo.