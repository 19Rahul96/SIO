import time
import uuid
from typing import Dict, List


class TraceEngine:
    def __init__(self):
        self._traces: Dict[str, Dict] = {}

    def start(self) -> str:
        trace_id = str(uuid.uuid4())
        self._traces[trace_id] = {
            "id": trace_id,
            "started_at": time.time(),
            "steps": [],
            "completed_at": None,
            "total_time": None,
        }
        return trace_id

    def add_step(self, trace_id: str, event: str, description: str) -> None:
        trace = self._traces.get(trace_id)
        if not trace:
            return
        trace["steps"].append({
            "event": event,
            "description": description,
            "timestamp": time.time(),
            "elapsed": round(time.time() - trace["started_at"], 3),
        })

    def finish(self, trace_id: str) -> Dict:
        trace = self._traces.get(trace_id)
        if trace:
            trace["completed_at"] = time.time()
            trace["total_time"] = round(trace["completed_at"] - trace["started_at"], 3)
        return trace or {}

    def get_trace(self, trace_id: str) -> Dict:
        return self._traces.get(trace_id, {})
