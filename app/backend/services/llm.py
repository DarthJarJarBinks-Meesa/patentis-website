import httpx
import json
import os
from typing import AsyncGenerator

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE = "https://api.groq.com/openai/v1"

INSTRUCTION_MODEL = os.getenv("INSTRUCTION_MODEL", "llama-3.3-70b-versatile")
REASONING_MODEL = os.getenv("REASONING_MODEL", "qwen/qwen3-32b")


def _headers(groq_api_key: str = "") -> dict:
    key = groq_api_key or GROQ_API_KEY
    if not key:
        raise ValueError("GROQ_API_KEY is not set — provide it in the app or add it to backend/.env")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def chat_complete(model: str, messages: list[dict], temperature: float = 0.7, groq_api_key: str = "") -> str:
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{GROQ_BASE}/chat/completions",
            headers=_headers(groq_api_key),
            json={"model": model, "messages": messages, "temperature": temperature, "stream": False},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]


async def chat_stream(
    model: str, messages: list[dict], temperature: float = 0.7, groq_api_key: str = ""
) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            f"{GROQ_BASE}/chat/completions",
            headers=_headers(groq_api_key),
            json={"model": model, "messages": messages, "temperature": temperature, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                raw = line[6:].strip()
                if raw == "[DONE]":
                    break
                data = json.loads(raw)
                content = data["choices"][0].get("delta", {}).get("content", "")
                if content:
                    yield content


async def extract_keywords(query: str, groq_api_key: str = "") -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a patent search expert. Extract search terms from the user's "
                "query and return ONLY a valid JSON object with no markdown, no extra text."
            ),
        },
        {
            "role": "user",
            "content": (
                f'Extract patent search keywords from this query: "{query}"\n\n'
                "Return a JSON object with:\n"
                "- keywords: list of 5-8 specific technical keywords\n"
                "- broad_terms: list of 2-3 broader category terms\n"
                "- cpc_hints: list of 1-3 likely CPC classification codes (e.g. A61B, H04L)\n\n"
                "Return ONLY valid JSON."
            ),
        },
    ]
    result = await chat_complete(INSTRUCTION_MODEL, messages, temperature=0.1, groq_api_key=groq_api_key)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        start = result.find("{")
        end = result.rfind("}")
        if start != -1 and end > start:
            return json.loads(result[start : end + 1])
        raise


async def check_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{GROQ_BASE}/models", headers=_headers())
            return {"provider": "groq", "connected": r.status_code == 200}
    except Exception:
        return {"provider": "groq", "connected": False}
