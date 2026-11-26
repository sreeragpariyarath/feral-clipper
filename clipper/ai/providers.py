"""Judge providers: one function per service, all taking the same prompt and returning the same shape.

    complete(system, user, cfg) -> Reply(text, tokens_in, tokens_out, source)

config.json picks the provider:
    "judge_provider": "claude" (default) | "gemini" | "ollama"
    "anthropic_model": "claude-haiku-5-5"        key: ANTHROPIC_API_KEY in .env
    "gemini_model":    "<model name>"             key: GEMINI_API_KEY in .env
    "ollama_model":    "<model name>"             local server, http://127.0.0.1:11434 (no key)

Every provider must return the judge's JSON object as text; clipper.ai.judge parses and validates it, so
switching providers changes nothing else in the pipeline.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class ProviderError(RuntimeError):
    """The provider could not give an answer (missing key, network, empty reply)."""


@dataclass(frozen=True)
class Reply:
    text: str
    tokens_in: int
    tokens_out: int
    source: str


def available(cfg: dict) -> bool:
    """True when the chosen provider has what it needs to run (a key, or a local server for Ollama)."""
    name = cfg.get("judge_provider", "claude")
    if name == "claude":
        return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    if name == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip()) and bool(cfg.get("gemini_model"))
    if name == "ollama":
        return bool(cfg.get("ollama_model"))
    return False


def complete(system: str, user: str, cfg: dict) -> Reply:
    name = cfg.get("judge_provider", "claude")
    fn = {"claude": _claude, "gemini": _gemini, "ollama": _ollama}.get(name)
    if fn is None:
        raise ProviderError(f"unknown judge_provider {name!r} (use claude, gemini or ollama)")
    return fn(system, user, cfg)


# ---------------------------------------------------------------- Claude (Anthropic SDK)
def _claude(system: str, user: str, cfg: dict) -> Reply:
    import anthropic

    model = cfg["anthropic_model"]
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise ProviderError("Claude declined this clip")
    text = "".join(b.text for b in resp.content if b.type == "text")
    if not text.strip():
        raise ProviderError(f"empty reply (stop_reason={resp.stop_reason})")
    return Reply(text, resp.usage.input_tokens, resp.usage.output_tokens, model)


# ---------------------------------------------------------------- HTTP helper for the others
def _post_json(url: str, body: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise ProviderError(f"HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProviderError(f"cannot reach {url.split('?')[0]}: {e}") from e


# ---------------------------------------------------------------- Gemini (REST)
def _gemini(system: str, user: str, cfg: dict) -> Reply:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = cfg.get("gemini_model")
    if not key or not model:
        raise ProviderError("Gemini needs GEMINI_API_KEY in .env and gemini_model in config.json")
    data = _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"systemInstruction": {"parts": [{"text": system}]},
         "contents": [{"role": "user", "parts": [{"text": user}]}],
         "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 2000}},
        {"x-goog-api-key": key},                     # header, so the key never appears in a URL or log
        timeout=120,
    )
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise ProviderError(f"empty reply from Gemini: {str(data)[:200]}")
    usage = data.get("usageMetadata") or {}
    return Reply(text, int(usage.get("promptTokenCount", 0)), int(usage.get("candidatesTokenCount", 0)), model)


# ---------------------------------------------------------------- Ollama (local model)
def _ollama(system: str, user: str, cfg: dict) -> Reply:
    model = cfg.get("ollama_model")
    if not model:
        raise ProviderError("Ollama needs ollama_model in config.json")
    host = cfg.get("ollama_host", "http://127.0.0.1:11434").rstrip("/")
    data = _post_json(f"{host}/api/chat",
                      {"model": model, "stream": False, "format": "json",
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                      {}, timeout=600)
    text = (data.get("message") or {}).get("content", "")
    if not text.strip():
        raise ProviderError("empty reply from Ollama")
    return Reply(text, int(data.get("prompt_eval_count", 0)), int(data.get("eval_count", 0)), f"ollama:{model}")
