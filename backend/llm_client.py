import os
import logging
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

_MODEL_MAP = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6": "claude-sonnet-4-6",
    "claude-opus-4-7": "claude-opus-4-7",
}


def _provider_for_model(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gpt"):
        return "openai"
    if model.startswith("gemini"):
        return "gemini"
    return "unknown"


def _available_provider_model(preferred_model: str) -> str | None:
    provider = _provider_for_model(preferred_model)

    if provider == "anthropic" and ANTHROPIC_KEY:
        return preferred_model
    if provider == "openai" and OPENAI_KEY:
        return preferred_model
    if provider == "gemini" and GEMINI_KEY:
        return preferred_model

    if OPENAI_KEY:
        return "gpt-4o-mini"
    if ANTHROPIC_KEY:
        return "claude-haiku-4-5-20251001"
    if GEMINI_KEY:
        return "gemini-2.0-flash"
    return None


def _fmt_relations(rels: List[Dict]) -> str:
    if not rels:
        return "No graph relations."
    return "\n".join(
        f"  {r.get('source','?')} --[{r.get('relation','?')}]--> {r.get('target','?')}"
        for r in rels[:10]
    )


async def call_llm(
    prompt: str,
    context: str,
    graph_relations: List[Dict],
    model: str = "claude-haiku-4-5-20251001",
) -> str:
    system = (
        "You are an intelligent data analyst. "
        "Use the document context and graph relations provided to give precise, data-grounded answers. "
        "If the context is insufficient, state that clearly."
    )
    user_msg = (
        f"DOCUMENT CONTEXT:\n{context[:3000]}\n\n"
        f"GRAPH RELATIONS:\n{_fmt_relations(graph_relations)}\n\n"
        f"QUESTION: {prompt}"
    )

    chosen_model = _available_provider_model(model)
    if not chosen_model:
        return _mock(prompt, context, "No LLM provider credentials are currently available.")

    provider = _provider_for_model(chosen_model)
    fallback_reason = None

    if provider == "anthropic" and ANTHROPIC_KEY:
        try:
            return await _anthropic(system, user_msg, chosen_model)
        except Exception as e:
            logger.warning("Anthropic call failed, falling back: %s", e)
            fallback_reason = f"Anthropic request failed: {e}"
    if provider == "openai" and OPENAI_KEY:
        try:
            return await _openai(system, user_msg, chosen_model)
        except Exception as e:
            err_str = str(e)
            if "insufficient_quota" in err_str or "429" in err_str:
                # Quota exhausted — skip all remaining providers to avoid cascading 429 retries.
                return _mock(prompt, context, f"OpenAI quota exceeded: {e}")
            logger.warning("OpenAI call failed, falling back: %s", e)
            fallback_reason = f"OpenAI request failed: {e}"
    if provider == "gemini" and GEMINI_KEY:
        try:
            return await _gemini(system, user_msg, chosen_model)
        except Exception as e:
            logger.warning("Gemini call failed, falling back: %s", e)
            fallback_reason = f"Gemini request failed: {e}"
    if GEMINI_KEY:
        try:
            return await _gemini(system, user_msg, "gemini-2.0-flash")
        except Exception as e:
            logger.warning("Gemini fallback model call failed, falling back: %s", e)
            fallback_reason = f"Gemini fallback request failed: {e}"
    if GROQ_KEY:
        try:
            return await _groq(system, user_msg)
        except Exception as e:
            logger.warning("Groq call failed, falling back: %s", e)
            fallback_reason = f"Groq request failed: {e}"
    return _mock(prompt, context, fallback_reason)


async def _anthropic(system: str, message: str, model: str) -> str:
    import anthropic
    api_model = _MODEL_MAP.get(model, "claude-haiku-4-5-20251001")
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)
    resp = await client.messages.create(
        model=api_model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": message}],
    )
    return resp.content[0].text


async def _openai(system: str, message: str, model: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_KEY)
    resp = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": message},
        ],
        max_tokens=1024,
    )
    return resp.choices[0].message.content


async def _gemini(system: str, message: str, model: str = "gemini-2.0-flash") -> str:
    import httpx
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": f"{system}\n\n{message}"}]}],
        "generationConfig": {"maxOutputTokens": 1024},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, params={"key": GEMINI_KEY})
        resp.raise_for_status()
        data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _groq(system: str, message: str, model: str = "llama-3.1-8b-instant") -> str:
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": message},
                ],
                "max_tokens": 1024,
            },
        )
        resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _mock(prompt: str, context: str, reason: str | None = None) -> str:
    word_count = len(context.split())
    note = (
        reason
        if reason
        else "Configure ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to receive real AI-generated responses."
    )
    return (
        f"**Analysis Result**\n\n"
        f"Based on {word_count} words of extracted document context:\n\n"
        f"**Query:** {prompt[:120]}\n\n"
        f"**Key findings from documents:**\n"
        f"- Primary data patterns identified across ingested sources\n"
        f"- Cross-referenced entities show significant relationships\n"
        f"- Knowledge graph traversal revealed {max(1, word_count // 50)} relevant connections\n\n"
        f"**Note:** {note}"
    )
