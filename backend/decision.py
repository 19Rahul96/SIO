from typing import Dict


class DecisionEngine:
    def analyze(self, prompt: str, slm_score: float, model_score: float = 0) -> Dict:
        complexity = self._complexity(prompt)
        savings_pct = min(95, round(slm_score * 0.82, 1))
        base_cost = 0.044
        est_cost = round(base_cost * max(0.05, 1 - slm_score / 100 * 0.9), 4)

        return {
            "task_complexity": complexity,
            "slm_confidence": round(slm_score, 1),
            "estimated_cost": est_cost,
            "token_saving_pct": savings_pct,
            "reasoning": self._reasoning(complexity, slm_score, est_cost),
        }

    def _complexity(self, prompt: str) -> str:
        words = len(prompt.split())
        has_analysis = any(w in prompt.lower() for w in ["analyse", "analyze", "explain", "why", "compare", "reason"])
        has_code = any(w in prompt.lower() for w in ["code", "script", "implement", "function"])
        if has_code or words > 100:
            return "High"
        if has_analysis or words > 35:
            return "Medium"
        return "Low"

    def _reasoning(self, complexity: str, score: float, cost: float) -> str:
        if score >= 80:
            match_desc = f"high SLM domain match ({score:.0f}%)"
        elif score >= 50:
            match_desc = f"moderate SLM domain match ({score:.0f}% — modified)"
        else:
            match_desc = "new SLM created for this domain"

        return (
            f"{complexity}-complexity query with {match_desc}. "
            f"Estimated cost: ${cost}. "
            f"SLM routing reduces token consumption significantly vs full LLM context."
        )
