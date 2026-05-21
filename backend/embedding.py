import os
import ssl
import pickle
import logging
import hashlib
import numpy as np
import faiss
from typing import List, Dict, Optional

# ML metrics contract import
from metrics import RunMetrics
import time
import json

logger = logging.getLogger(__name__)

# ── SSL bypass for corporate proxy / SSL-inspection environments ──────────────
# Must execute before any huggingface_hub / sentence_transformers import so that
# every outbound HTTPS request (model download, metadata fetch) skips cert checks.
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFY", "1")
ssl._create_default_https_context = ssl._create_unverified_context  # stdlib http.client

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    import requests as _req
    _orig_send = _req.Session.send
    def _no_verify_send(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_send(self, *args, **kwargs)
    _req.Session.send = _no_verify_send
except Exception:
    pass
# ─────────────────────────────────────────────────────────────────────────────

FAISS_DIR = "data/faiss"
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = f"{FAISS_DIR}/index.faiss"
CHUNKS_PATH = f"{FAISS_DIR}/chunks.pkl"
DIMENSION = 384


class EmbeddingStore:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.index: faiss.IndexFlatIP = None
        self.chunks: List[Dict] = []
        self._load()

    def _model_instance(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # Prefer local cache to avoid long SSL/network retry delays.
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
                logger.info(f"Loaded SentenceTransformer: {self.model_name}")
            except BaseException as e:
                logger.warning(
                    "SentenceTransformer load failed; using deterministic fallback embeddings. "
                    "Reason: %s",
                    e,
                )
                self._model = False
        return self._model

    def _fallback_embed(self, text: str) -> np.ndarray:
        # Deterministic local embedding fallback so API stays functional offline/SSL-blocked.
        vec = np.zeros(DIMENSION, dtype=np.float32)
        if not text:
            return vec

        tokens = text.lower().split()
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8", errors="ignore")).digest()
            for i in range(0, len(digest), 2):
                idx = ((digest[i] << 8) | digest[i + 1]) % DIMENSION
                sign = 1.0 if (digest[i] & 1) else -1.0
                vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def _load(self):
        if os.path.exists(INDEX_PATH) and os.path.exists(CHUNKS_PATH):
            try:
                self.index = faiss.read_index(INDEX_PATH)
                with open(CHUNKS_PATH, "rb") as f:
                    self.chunks = pickle.load(f)
                logger.info(f"FAISS index loaded: {len(self.chunks)} chunks")
                return
            except Exception as e:
                logger.error(f"FAISS load failed: {e}")
        self._init_index()

    def _init_index(self):
        self.index = faiss.IndexFlatIP(DIMENSION)
        self.chunks = []

    def _save(self):
        faiss.write_index(self.index, INDEX_PATH)
        with open(CHUNKS_PATH, "wb") as f:
            pickle.dump(self.chunks, f)

    def embed_text(self, text: str) -> np.ndarray:
        model = self._model_instance()
        if model is False:
            return self._fallback_embed(text)

        try:
            emb = model.encode([text], normalize_embeddings=True)[0]
            return emb.astype(np.float32)
        except Exception as e:
            logger.warning("Embedding encode failed; using fallback embedding. Reason: %s", e)
            self._model = False
            return self._fallback_embed(text)

    def search(self, query_emb: np.ndarray, k: int = 5, file_ids: Optional[List[str]] = None) -> List[Dict]:
        # ...existing code...
        # This is a stub for metrics emission; real metrics can be added as available.
        try:
            metrics_artifact = RunMetrics(
                run_id=f"retrieval_{int(time.time()*1000)}",
                stage="retrieval_ranking",
                timestamp=str(time.time()),
                classification=None,
                retrieval=None,
                calibration=None,
                hallucination=None,
                extra={
                    "k": k,
                    "file_ids": file_ids,
                },
                version="1.0",
            )
            with open(f"data/processed/retrieval_metrics_{int(time.time()*1000)}.json", "w") as f:
                f.write(metrics_artifact.json(indent=2))
        except Exception as e:
            pass
        # ...existing code continues...

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        try:
            model = self._model_instance()
        except BaseException as e:
            logger.warning("Embedding model initialization failed; using fallback embeddings. Reason: %s", e)
            self._model = False
            return np.vstack([self._fallback_embed(t) for t in texts]).astype(np.float32)

        if model is False:
            return np.vstack([self._fallback_embed(t) for t in texts]).astype(np.float32)

        try:
            embs = model.encode(
                texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
            )
            return embs.astype(np.float32)
        except BaseException as e:
            logger.warning("Batch embedding failed; using fallback embeddings. Reason: %s", e)
            self._model = False
            return np.vstack([self._fallback_embed(t) for t in texts]).astype(np.float32)

    def add_chunks(self, file_id: str, chunks: List[Dict]):
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = self._embed_batch(texts)
        self.index.add(embeddings)
        for i, chunk in enumerate(chunks):
            self.chunks.append({
                "file_id": file_id,
                "text": chunk["text"],
                "chunk_idx": chunk.get("idx", i),
            })
        self._save()
        logger.info(f"Indexed {len(chunks)} chunks for {file_id}")

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5,
        file_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        if len(self.chunks) == 0:
            return []
        k_fetch = min(k * 4, len(self.chunks))
        scores, indices = self.index.search(query_embedding.reshape(1, -1), k_fetch)
        results: List[Dict] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.chunks):
                continue
            chunk = self.chunks[idx]
            if file_ids and chunk["file_id"] not in file_ids:
                continue
            results.append({**chunk, "score": float(score)})
            if len(results) >= k:
                break
        return results
