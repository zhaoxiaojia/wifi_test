"""Unified backend for AI chat providers.

This module defines a small registry of free-tier or trial-friendly
LLM HTTP APIs and exposes a single entry point for the AI chat tool
to send messages.  Each provider is described declaratively so that
new APIs can be added without touching the view/controller layers.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from src.util.constants import get_config_base


@dataclass(frozen=True)
class AiProvider:
    """Declarative description of a single AI chat provider."""

    model_id: str
    title: str
    chat_url: str
    model: str
    api_key_env: str
    signup_url: str


# NOTE: These providers are chosen to use well-known model families
# where possible (OpenAI ChatGPT, Llama 3, etc.).  All of them are
# official APIs that require the user to configure an API key via
# environment variables.
AVAILABLE_PROVIDERS: Dict[str, AiProvider] = {
    "openai-gpt4o-mini": AiProvider(
        model_id="openai-gpt4o-mini",
        title="OpenAI ChatGPT (GPT-4o mini)",
        chat_url="https://api.openai.com/v1/chat/completions",
        model="gpt-4o-mini",
        api_key_env="OPENAI_API_KEY",
        signup_url="https://platform.openai.com/",
    ),
    "deepseek-chat": AiProvider(
        model_id="deepseek-chat",
        title="DeepSeek Chat",
        chat_url="https://api.deepseek.com/chat/completions",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        signup_url="https://platform.deepseek.com/signin",
    ),
    "groq-llama3-8b": AiProvider(
        model_id="groq-llama3-8b",
        title="Groq Llama 3 8B",
        chat_url="https://api.groq.com/openai/v1/chat/completions",
        model="llama-3.1-8b-instant",
        api_key_env="GROQ_API_KEY",
        signup_url="https://console.groq.com/",
    ),
}


def list_model_ids() -> List[str]:
    """Return the list of model ids used by the UI combo box."""
    return list(AVAILABLE_PROVIDERS.keys())


def list_models_for_ui() -> List[Tuple[str, str]]:
    """Return (model_id, title) pairs for use in the model combo box."""
    items: List[Tuple[str, str]] = []
    for model_id, provider in AVAILABLE_PROVIDERS.items():
        items.append((model_id, provider.title))
    return items


def get_signup_url(model_id: str) -> str:
    """Return the signup/docs URL for the given model id."""
    return AVAILABLE_PROVIDERS[model_id].signup_url


def _keys_path() -> Path:
    return get_config_base().resolve() / "ai_keys.json"


def load_api_key(model_id: str) -> str:
    """Return a stored API key for the given model id, if any."""
    path = _keys_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        key = data.get(model_id, "")
        if isinstance(key, str):
            return key
    return ""


def store_api_key(model_id: str, api_key: str) -> None:
    """Persist an API key for the given model id."""
    path = _keys_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {}
    data[model_id] = api_key
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def send_chat_completion(model_id: str, user_text: str) -> str:
    """Send a single-turn chat completion request for the given model_id.

    All providers use an OpenAI-compatible /chat/completions-style API.
    """
    provider = AVAILABLE_PROVIDERS[model_id]
    api_key = load_api_key(model_id).strip()
    if not api_key:
        api_key = os.environ.get(provider.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"Missing API key in env var {provider.api_key_env}.")

    payload = {
        "model": provider.model,
        "messages": [{"role": "user", "content": user_text}],
        "temperature": 0.7,
    }
    print(f"[DEBUG_AICHAT] send_chat_completion model_id={model_id!r}, url={provider.chat_url!r}")  # DEBUG_AICHAT
    print(f"[DEBUG_AICHAT] payload={payload!r}")  # DEBUG_AICHAT
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    request = Request(provider.chat_url, data=data, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        snippet = body[:300].strip().replace("\n", " ")
        raise RuntimeError(f"HTTP {exc.code}: {exc.reason}. Response: {snippet}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error calling provider: {exc.reason}") from exc

    print(f"[DEBUG_AICHAT] raw_response={raw[:500]!r}")  # DEBUG_AICHAT
    document = json.loads(raw)
    choice = document["choices"][0]
    message = choice["message"]["content"]
    return str(message)


__all__ = [
    "AiProvider",
    "AVAILABLE_PROVIDERS",
    "list_model_ids",
    "list_models_for_ui",
    "get_signup_url",
    "load_api_key",
    "store_api_key",
    "send_chat_completion",
]
