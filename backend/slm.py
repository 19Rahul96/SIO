import json
import os
import time
import uuid
import logging
import hashlib
import numpy as np
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = "data/slm_registry.json"
os.makedirs("data", exist_ok=True)


def _cosine(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


class SLMRegistry:
    def __init__(self):
        self._model = None
        self.registry: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if os.path.exists(REGISTRY_PATH):
            try:
                with open(REGISTRY_PATH) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Registry load failed: {e}")
        return []

    def _save(self):
        with open(REGISTRY_PATH, "w") as f:
            json.dump(self.registry, f, indent=2)

    def _embed(self, text: str) -> List[float]:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.warning(
                    "SLM embedding model load failed; using deterministic fallback embeddings. "
                    "Reason: %s",
                    e,
                )
                self._model = False

        if self._model is False:
            return self._fallback_embed(text)

        try:
            emb = self._model.encode([text], normalize_embeddings=True)[0]
            return emb.tolist()
        except Exception as e:
            logger.warning("SLM embedding encode failed; using fallback embedding. Reason: %s", e)
            self._model = False
            return self._fallback_embed(text)

    def _fallback_embed(self, text: str) -> List[float]:
        dim = 384
        vec = np.zeros(dim, dtype=np.float32)
        if not text:
            return vec.tolist()

        for tok in text.lower().split():
            digest = hashlib.sha256(tok.encode("utf-8", errors="ignore")).digest()
            for i in range(0, len(digest), 2):
                idx = ((digest[i] << 8) | digest[i + 1]) % dim
                sign = 1.0 if (digest[i] & 1) else -1.0
                vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def _normalize_file_ids(self, file_ids: Optional[List[str]]) -> List[str]:
        if not file_ids:
            return []
        return sorted({fid for fid in file_ids if fid})

    def _scope_key(self, file_ids: List[str]) -> str:
        if not file_ids:
            return "global"
        raw = "|".join(file_ids)
        return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _scope_overlap(self, a: List[str], b: List[str]) -> float:
        if not a or not b:
            return 0.0
        sa, sb = set(a), set(b)
        return len(sa & sb) / max(1, len(sa))

    def match(self, prompt: str, file_ids: Optional[List[str]] = None) -> Dict:
        prompt_emb = self._embed(prompt)
        req_file_ids = self._normalize_file_ids(file_ids)

        best_score = 0.0
        best_slm: Optional[Dict] = None
        best_overlap = 0.0
        for slm in self.registry:
            vec = slm.get("embedding_vector", [])
            if not vec:
                continue
            raw = _cosine(prompt_emb, vec)
            semantic_score = (raw + 1) / 2 * 100

            slm_scope = self._normalize_file_ids(slm.get("source_file_ids", []))
            overlap = self._scope_overlap(req_file_ids, slm_scope) if req_file_ids else 1.0

            # Prefer SLMs trained on the same selected dataset, but do not hard-block
            # strong semantic matches from being reused across related datasets.
            score_100 = semantic_score * (0.65 + 0.35 * overlap)
            if score_100 > best_score:
                best_score = score_100
                best_slm = slm
                best_overlap = overlap

        score = round(best_score, 1)

        if score >= 80 and best_slm:
            decision = "reuse"
            self._increment(best_slm["id"])
            slm_out = best_slm
        elif score >= 50 and best_slm:
            decision = "modify"
            slm_out = self._modify(best_slm, prompt_emb, req_file_ids)
        else:
            decision = "create"
            slm_out = self._create(prompt, prompt_emb, req_file_ids)

        return {
            "decision": decision,
            "score": score,
            "slm": slm_out,
            "scope_overlap": round(best_overlap, 2),
            "scope_preference_applied": bool(req_file_ids),
            "threshold_80": score >= 80,
            "threshold_50": 50 <= score < 80,
            "below_50": score < 50,
        }

    def _increment(self, slm_id: str):
        for s in self.registry:
            if s["id"] == slm_id:
                s["usage_count"] = s.get("usage_count", 0) + 1
                s["last_used"] = time.time()
                break
        self._save()

    def _modify(self, slm: Dict, new_emb: List[float], file_ids: Optional[List[str]] = None) -> Dict:
        old = np.array(slm["embedding_vector"])
        blended = old * 0.7 + np.array(new_emb) * 0.3
        norm = np.linalg.norm(blended)
        if norm > 0:
            blended = blended / norm
        slm["embedding_vector"] = blended.tolist()
        slm["usage_count"] = slm.get("usage_count", 0) + 1
        slm["last_used"] = time.time()
        slm["parameters"]["context_window"] = slm["parameters"].get("context_window", 2048) + 128
        if file_ids:
            merged = self._normalize_file_ids(slm.get("source_file_ids", []) + list(file_ids))
            slm["source_file_ids"] = merged
            slm["scope_key"] = self._scope_key(merged)
        self._save()
        return slm

    def _create(self, prompt: str, emb: List[float], file_ids: Optional[List[str]] = None) -> Dict:
        normalized_ids = self._normalize_file_ids(file_ids)
        slm_id = str(uuid.uuid4())
        name = self._gen_name(prompt)
        slm = {
            "id": slm_id,
            "name": name,
            "embedding_vector": emb,
            "source_file_ids": normalized_ids,
            "scope_key": self._scope_key(normalized_ids),
            "parameters": {
                "context_window": 2048,
                "temperature": 0.7,
                "max_tokens": 512,
                "domain": self._domain(prompt),
            },
            "usage_count": 1,
            "created_at": time.time(),
            "last_used": time.time(),
            "age_days": 0,
        }
        self.registry.append(slm)
        self._save()
        logger.info(f"Created SLM: {name} ({slm_id})")
        return slm

    def _gen_name(self, prompt: str) -> str:
        words = [w for w in prompt.lower().split()[:4] if len(w) > 2]
        base = "-".join(words[:3]) or "general"
        count = sum(1 for s in self.registry if s.get("name", "").startswith(base))
        return f"{base}-v{count + 1}"

    def _domain(self, prompt: str) -> str:
        pl = prompt.lower()
        for domain, kw in {
            "finance": ["revenue", "profit", "cost", "budget", "financial"],
            "hr": ["employee", "policy", "hr", "staff", "human resource"],
            "inventory": ["inventory", "stock", "reorder", "warehouse", "supply"],
            "legal": ["contract", "legal", "law", "compliance"],
            "analytics": ["analyse", "trend", "data", "report", "insight"],
        }.items():
            if any(k in pl for k in kw):
                return domain
        return "general"

    def get(self, slm_id: str) -> Optional[Dict]:
        return next((s for s in self.registry if s["id"] == slm_id), None)

    def list_all(self) -> List[Dict]:
        return self.registry

    def update_usage(self, slm_id: str):
        self._increment(slm_id)

    def get_recent_sessions(self) -> List[Dict]:
        sorted_slms = sorted(self.registry, key=lambda x: x.get("last_used", 0), reverse=True)
        return [
            {
                "name": s["name"],
                "slm_id": s["id"],
                "usage_count": s.get("usage_count", 0),
                "domain": s.get("parameters", {}).get("domain", "general"),
                "last_used": s.get("last_used"),
            }
            for s in sorted_slms[:5]
        ]
