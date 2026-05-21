"""Route LLM calls by task (platform-managed inference)."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import httpx

from patentis_platform.config import get_settings


class Task(str, Enum):
    KEYWORD_EXTRACT = "keyword_extract"
    WHITESPACE_BRIEF = "whitespace_brief"
    GAP_IDENTIFICATION = "gap_identification"
    FIGURE_CAPTIONING = "figure_captioning"
    PRIOR_ART_SUMMARY = "prior_art_summary"
    ANALYST_CHAT = "analyst_chat"


_TASK_TEMPERATURE: dict[Task, float] = {
    Task.KEYWORD_EXTRACT: 0.1,
    Task.WHITESPACE_BRIEF: 0.25,
    Task.GAP_IDENTIFICATION: 0.25,
    Task.FIGURE_CAPTIONING: 0.2,
    Task.PRIOR_ART_SUMMARY: 0.15,
    Task.ANALYST_CHAT: 0.5,
}


def _chat_endpoint() -> tuple[str, dict[str, str], dict[str, Any]]:
    settings = get_settings()
    if settings.azure_openai_endpoint and settings.azure_openai_api_key and settings.azure_openai_deployment_chat:
        url = (
            settings.azure_openai_endpoint.rstrip("/")
            + f"/openai/deployments/{settings.azure_openai_deployment_chat}"
            + "/chat/completions?api-version=2024-08-01-preview"
        )
        return url, {"api-key": settings.azure_openai_api_key, "Content-Type": "application/json"}, {}
    if not settings.openai_api_key:
        return "", {}, {}
    url = settings.openai_base_url.rstrip("/") + "/chat/completions"
    return url, {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}, {
        "model": settings.openai_chat_model
    }


async def chat_json(
    system: str,
    user: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    url, headers, model_field = _chat_endpoint()
    if not url:
        return {}
    payload = {
        **model_field,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            return {}
        content = r.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


async def chat_text(system: str, user: str, temperature: float = 0.3) -> str:
    url, headers, model_field = _chat_endpoint()
    if not url:
        return ""
    payload = {
        **model_field,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            return ""
        return r.json()["choices"][0]["message"]["content"]


class ModelRouter:
    async def call_json(self, task: Task, system: str, user: str) -> dict[str, Any]:
        return await chat_json(system, user, temperature=_TASK_TEMPERATURE.get(task, 0.2))

    async def call_text(self, task: Task, system: str, user: str) -> str:
        return await chat_text(system, user, temperature=_TASK_TEMPERATURE.get(task, 0.3))


model_router = ModelRouter()


async def chat_vision_caption(images_b64_or_urls: list[dict[str, Any]], prompt: str) -> str:
    settings = get_settings()
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}, *images_b64_or_urls]
    messages = [{"role": "user", "content": content}]
    if not settings.openai_api_key and not settings.azure_openai_api_key:
        return "Vision model not configured — provide image placeholders in multimodal workflow."
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        url = (
            settings.azure_openai_endpoint.rstrip("/")
            + f"/openai/deployments/{settings.azure_openai_deployment_chat}"
            + "/chat/completions?api-version=2024-08-01-preview"
        )
        headers = {"api-key": settings.azure_openai_api_key, "Content-Type": "application/json"}
        model_field: dict[str, Any] = {}
    else:
        url = settings.openai_base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
        model_field = {"model": settings.openai_vision_model}
    payload = {**model_field, "messages": messages, "max_tokens": 800}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            return ""
        return r.json()["choices"][0]["message"]["content"]
