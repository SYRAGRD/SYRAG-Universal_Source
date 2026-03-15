from __future__ import annotations

import json
import logging
import os
from typing import Any, Callable, Dict, Optional

import requests


logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    pass


def analyze_with_provider(
    provider: str,
    model: str,
    prompt: str,
    cfg: Dict[str, Any],
    api_key_override: str = "",
    timeout_s: int = 120,
    chunk_timeout: int = 120,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """Send a prompt to the selected provider and return plain text response.

    Supported providers:
    - ollama
    - openrouter
    - openai_compatible

    chunk_timeout: for Ollama streaming, max seconds to wait between token
    chunks. Set by the user in the GUI. 120s is a safe default for 7-8B CPU.
    """
    provider = (provider or "").strip()
    model = (model or "").strip()
    prompt = prompt or ""

    if not provider:
        raise LLMClientError("Provider is required")
    if not model:
        raise LLMClientError("Model is required")
    if not prompt.strip():
        raise LLMClientError("Prompt is empty")
    if timeout_s <= 0:
        raise LLMClientError("timeout_s must be > 0")

    provider_cfg = cfg.get("llm", {}).get("providers", {}).get(provider, {})
    timeout_effective = int(provider_cfg.get("timeout_s", timeout_s))
    timeout_effective = max(timeout_effective, 1)

    if provider == "ollama":
        base = provider_cfg.get("base_url", "http://localhost:11434").rstrip("/")
        url = f"{base}/api/generate"
        base_num_predict = int(provider_cfg.get("num_predict", 256))
        base_num_ctx = int(provider_cfg.get("num_ctx", 3072))
        ollama_options = {
            "num_predict": min(max(base_num_predict, 64), 320),
            "num_ctx": min(max(base_num_ctx, 1024), 4096),
        }
        # Use stream=True so tokens arrive incrementally — no blocking wait for
        # the full response, no read timeout on long generations.
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "options": ollama_options,
        }
        connect_timeout = 15
        effective_chunk_timeout = max(10, chunk_timeout)
        logger.info(
            "LLM request provider=ollama model=%s (streaming, chunk_timeout=%s)",
            model, effective_chunk_timeout,
        )
        if progress_callback:
            progress_callback("Connecting to Ollama...")
        try:
            r = requests.post(
                url, json=payload, stream=True,
                timeout=(connect_timeout, effective_chunk_timeout),
            )
        except requests.RequestException as e:
            raise LLMClientError(f"Ollama connection error: {e}") from e
        if r.status_code >= 400:
            msg = f"Ollama error {r.status_code}: {r.text[:400]}"
            if "not found" in r.text.lower() and "model" in r.text.lower():
                msg += " | Hint: run `ollama list` and choose an installed model in the GUI."
            raise LLMClientError(msg)
        if progress_callback:
            progress_callback("Receiving response...")
        parts: list[str] = []
        try:
            for raw_line in r.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except ValueError:
                    continue
                token = chunk.get("response", "")
                if token:
                    parts.append(token)
                    if progress_callback and len(parts) % 40 == 0:
                        progress_callback(f"Generating... (~{len(parts)} tokens)")
                if chunk.get("done", False):
                    break
        except requests.ReadTimeout:
            if parts:
                logger.warning("Ollama stream chunk timeout after %d tokens", len(parts))
                return "".join(parts) + "\n\n[Note: output truncated — chunk timeout reached]"
            raise LLMClientError(
                f"Ollama stream chunk timed out with no output (chunk_timeout={effective_chunk_timeout}s).\n"
                "Increase the 'Chunk timeout' value in the GUI and retry."
            )
        except requests.RequestException as e:
            if parts:
                return "".join(parts) + f"\n\n[Stream interrupted: {e}]"
            raise LLMClientError(f"Ollama stream error: {e}") from e
        text = "".join(parts)
        if not text:
            raise LLMClientError("Ollama returned empty response")
        return text

    if provider in {"openrouter", "openai_compatible"}:
        base = provider_cfg.get("base_url", "").rstrip("/")
        if not base:
            raise LLMClientError(f"Missing base_url for provider {provider}")

        env_key_name = provider_cfg.get("api_key_env", "")
        api_key = api_key_override.strip() or (os.getenv(env_key_name, "") if env_key_name else "")
        if not api_key:
            raise LLMClientError(
                f"Missing API key. Set environment variable: {env_key_name or 'API_KEY'}"
            )

        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        logger.info("LLM request provider=%s model=%s", provider, model)
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout_effective)
        except requests.RequestException as e:
            raise LLMClientError(f"{provider} connection error: {e}") from e
        if r.status_code >= 400:
            if r.status_code in {401, 403}:
                raise LLMClientError(f"{provider} auth error {r.status_code}: check API key")
            if r.status_code == 429:
                raise LLMClientError(f"{provider} rate-limited (429): retry later")
            raise LLMClientError(f"{provider} error {r.status_code}: {r.text[:400]}")
        try:
            data = r.json()
        except ValueError as e:
            raise LLMClientError(f"{provider} returned non-JSON response") from e

        choices = data.get("choices", [])
        if not isinstance(choices, list) or not choices:
            raise LLMClientError(f"{provider} response format invalid: missing choices")
        content = choices[0].get("message", {}).get("content", "")
        if not isinstance(content, str):
            raise LLMClientError(f"{provider} response format invalid: missing content text")
        return content

    raise LLMClientError(f"Unsupported provider: {provider}")
