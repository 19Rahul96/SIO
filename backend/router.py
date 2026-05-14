from typing import List, Dict


class ModelRouter:
    MODELS = [
        {
            "id": "claude-haiku-4-5-20251001",
            "name": "claude-haiku-4-5",
            "provider": "Anthropic",
            "cost_per_1k": 0.00025,
            "speed": "fast",
            "context_window": 200000,
            "strengths": ["speed", "efficiency", "instruction_following"],
        },
        {
            "id": "claude-sonnet-4-6",
            "name": "claude-sonnet-4-6",
            "provider": "Anthropic",
            "cost_per_1k": 0.003,
            "speed": "medium",
            "context_window": 200000,
            "strengths": ["reasoning", "analysis", "coding"],
        },
        {
            "id": "gpt-4o-mini",
            "name": "gpt-4o-mini",
            "provider": "OpenAI",
            "cost_per_1k": 0.00015,
            "speed": "fast",
            "context_window": 128000,
            "strengths": ["speed", "efficiency"],
        },
        {
            "id": "gpt-4o",
            "name": "gpt-4o",
            "provider": "OpenAI",
            "cost_per_1k": 0.005,
            "speed": "medium",
            "context_window": 128000,
            "strengths": ["reasoning", "multimodal"],
        },
        {
            "id": "gemini-2.0-flash",
            "name": "gemini-2.0-flash",
            "provider": "Google",
            "cost_per_1k": 0.00010,
            "speed": "fast",
            "context_window": 1000000,
            "strengths": ["structured_data", "long_context"],
        },
    ]

    def route(
        self,
        prompt: str,
        slm_score: float,
        context_size: int = 500,
        graph_density: float = 0.0,
    ) -> List[Dict]:
        complexity = self._complexity(prompt)
        ranked = []
        for model in self.MODELS:
            score = self._score(model, complexity, slm_score, context_size, graph_density)
            ranked.append({
                "model": model,
                "score": round(score, 1),
                "complexity": complexity,
                "recommendation": self._label(score, complexity),
                "estimated_cost": self._cost(model, context_size, len(prompt.split())),
                "graph_density": round(graph_density, 6),
                "chosen": False,
            })
        ranked.sort(key=lambda x: x["score"], reverse=True)
        if ranked:
            ranked[0]["chosen"] = True
        return ranked

    def _complexity(self, prompt: str) -> str:
        words = len(prompt.split())
        pl = prompt.lower()
        has_analysis = any(w in pl for w in ["analyse", "analyze", "explain", "compare", "why"])
        has_code = any(w in pl for w in ["code", "script", "implement", "function"])
        if has_code or words > 100:
            return "high"
        if has_analysis or words > 35:
            return "medium"
        return "low"

    def _score(self, model: Dict, complexity: str, slm_score: float, ctx: int, graph_density: float) -> float:
        score = 50.0
        if complexity == "low" and model["speed"] == "fast":
            score += 25
        elif complexity == "medium" and model["speed"] in ("fast", "medium"):
            score += 20
        elif complexity == "high" and "reasoning" in model["strengths"]:
            score += 25

        # If graph is dense, reasoning-oriented models are more valuable for relation synthesis.
        if graph_density >= 0.008 and any(s in model["strengths"] for s in ("reasoning", "analysis")):
            score += 8
        elif graph_density < 0.002 and model["speed"] == "fast":
            # Sparse graph means heavier reliance on vector snippets: prefer fast parsers.
            score += 5

        if slm_score >= 80:
            score += max(0, 20 - model["cost_per_1k"] * 2000)
        if complexity == "low" and model["cost_per_1k"] > 0.003:
            score -= 20
        return min(100, max(0, score))

    def _label(self, score: float, complexity: str) -> str:
        if score >= 90:
            return "Optimal choice"
        if score >= 75:
            return "Good alternative"
        if score >= 60:
            return "Viable option"
        return "Not recommended"

    def _cost(self, model: Dict, ctx: int, prompt_words: int) -> float:
        tokens = ctx + prompt_words * 1.3 + 300
        return round(tokens / 1000 * model["cost_per_1k"], 5)
