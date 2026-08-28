"""A small provider-agnostic chat client, stdlib only.

Used for exactly one thing: writing seed scenarios. Everything downstream of
generation -- mutation, execution, detection, scoring -- runs without a model,
which is why the core has no dependencies and why a cached suite replays offline.

Free providers are first-class here. A reliability tool nobody can afford to run
does not get run.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class LLMError(Exception):
    pass


class MissingAPIKeyError(LLMError):
    pass


@dataclass(frozen=True)
class Provider:
    name: str
    base_url: str
    env_key: str | None
    default_model: str


# Free tiers rate-limit by tokens per minute, and a suite makes hundreds of
# calls in seconds, so 429s are the normal case rather than an exception.
# Providers tell us how long to wait; honouring that is the difference between
# a run that completes and one that reports nothing.
_RETRY_AFTER = re.compile(r"try again in ([0-9.]+)s", re.I)
MAX_RETRIES = 5


PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
        "GROQ_API_KEY",
        # Model availability on Groq changes; pass --model if this one is gone.
        # `agentcheck models --provider groq` lists what a key can actually use.
        "openai/gpt-oss-120b",
    ),
    "openrouter": Provider(
        "openrouter",
        "https://openrouter.ai/api/v1/chat/completions",
        "OPENROUTER_API_KEY",
        "meta-llama/llama-3.3-70b-instruct:free",
    ),
    "together": Provider(
        "together",
        "https://api.together.xyz/v1/chat/completions",
        "TOGETHER_API_KEY",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    ),
    # Local, no key, no network egress. The offline fallback.
    "ollama": Provider(
        "ollama",
        "http://localhost:11434/v1/chat/completions",
        None,
        "llama3.1",
    ),
}

FREE_OPTIONS = """No LLM provider configured.

Only two things need a model: generating new seed scenarios, and running the
built-in LLM agent (--agent llm). Everything else -- the mutation ladder, the
mock world, all ten detectors, scoring, and reports -- runs without one.

Free options:
  Groq        export GROQ_API_KEY=...        https://console.groq.com/keys
  OpenRouter  export OPENROUTER_API_KEY=...  https://openrouter.ai/keys
  Ollama      run it locally, no key needed  https://ollama.com

Then re-run, or pass --provider explicitly."""


def resolve_provider(name: str | None = None) -> Provider:
    """Pick a provider from an explicit name, the environment, or a present key."""
    chosen = name or os.environ.get("AGENTCHECK_LLM_PROVIDER")
    if chosen:
        if chosen not in PROVIDERS:
            raise LLMError(f"unknown provider {chosen!r}; expected one of {sorted(PROVIDERS)}")
        return PROVIDERS[chosen]

    for provider in PROVIDERS.values():
        if provider.env_key and os.environ.get(provider.env_key):
            return provider
    raise MissingAPIKeyError(FREE_OPTIONS)


def chat_message(
    messages: list[dict[str, Any]],
    *,
    provider: str | Provider | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8000,
    timeout: int = 120,
    tools: list[dict[str, Any]] | None = None,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """Send a chat completion and return the whole assistant message.

    Returns the raw message rather than just its text because an agent needs the
    `tool_calls` array. Every provider here speaks the OpenAI-compatible shape.
    """
    prov = provider if isinstance(provider, Provider) else resolve_provider(provider)
    payload: dict[str, Any] = {
        "model": model or prov.default_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    body = _post(prov, payload, timeout=timeout, max_retries=max_retries)
    try:
        return body["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape from {prov.name}: {body}") from exc


def chat(
    messages: list[dict[str, Any]],
    *,
    provider: str | Provider | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8000,
    timeout: int = 120,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Send a chat completion request and return the assistant's text.

    Temperature defaults to 0: generation is cached, and a cache whose contents
    shift between fills is not much of a cache.
    """
    prov = provider if isinstance(provider, Provider) else resolve_provider(provider)
    body = _post(
        prov,
        {
            "model": model or prov.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
        max_retries=max_retries,
    )
    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape from {prov.name}: {body}") from exc


# Points every provider at a different endpoint. For self-hosted or
# OpenAI-compatible gateways, and it is how the HTTP path gets covered by tests
# without reaching a real provider.
BASE_URL_OVERRIDE = "AGENTCHECK_LLM_BASE_URL"


def _retry_delay(detail: str, attempt: int) -> float:
    """Seconds to wait, preferring the provider's own advice."""
    match = _RETRY_AFTER.search(detail)
    if match:
        # A small margin: the window is measured provider-side, and waking up
        # exactly on the boundary just earns another 429.
        return min(float(match.group(1)) + 0.5, 30.0)
    return min(2.0**attempt, 30.0)


def _post(
    prov: Provider, payload: dict[str, Any], *, timeout: int, max_retries: int = MAX_RETRIES
) -> dict[str, Any]:
    """POST a chat-completions request and return the decoded body.

    Retries on rate limits only. Other errors are the caller's problem and are
    surfaced immediately rather than being retried into a longer failure.
    """
    url = os.environ.get(BASE_URL_OVERRIDE) or prov.base_url
    headers = {"content-type": "application/json"}
    if prov.env_key:
        key = os.environ.get(prov.env_key)
        if not key and not os.environ.get(BASE_URL_OVERRIDE):
            raise MissingAPIKeyError(
                f"{prov.name} selected but {prov.env_key} is not set.\n\n{FREE_OPTIONS}"
            )
        if key:
            headers["authorization"] = f"Bearer {key}"

    # Several providers sit behind Cloudflare, which 403s the default
    # "Python-urllib/3.x" user agent outright. Identifying ourselves avoids a
    # confusing failure that looks like a bad API key.
    headers["user-agent"] = "agentcheck/0.1"

    data = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries + 1):
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 413) and attempt < max_retries:
                detail = exc.read().decode("utf-8", "replace")
                time.sleep(_retry_delay(detail, attempt))
                continue
            raise _http_error(prov, exc) from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"could not reach {prov.name} at {url}: {exc.reason}") from exc

    raise LLMError(f"{prov.name}: still rate limited after {max_retries} retries")


def _http_error(prov: Provider, exc: urllib.error.HTTPError) -> LLMError:
    """Turn a provider HTTP error into one carrying an actionable next step.

    Providers explain quota and model problems in the response body, and hiding
    it turns a two-second fix into a debugging session.
    """
    detail = exc.read().decode("utf-8", "replace")[:600]
    hint = ""
    if exc.code == 404 and "model" in detail:
        hint = (
            f"\n\nThat model is not available on this key. List what is:\n"
            f"    agentcheck models --provider {prov.name}"
        )
    elif exc.code in (429, 413):
        hint = (
            "\n\nThis is a per-minute token budget, not a payload size. "
            "Retries were already exhausted; wait a minute, lower --max-tokens, "
            "or run a smaller suite with --seeds-only."
        )
    return LLMError(f"{prov.name} returned HTTP {exc.code}: {detail}{hint}")


def extract_json(text: str) -> object:
    """Pull a JSON value out of a model response.

    Models wrap JSON in prose and fences no matter how firmly the prompt says
    not to, so this is a normal path rather than an error case.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"no JSON found in model response: {text[:300]}")


def list_models(provider: str | Provider | None = None, *, timeout: int = 30) -> list[str]:
    """Model ids a key can actually use.

    Provider catalogues change, so a hard-coded default eventually 404s. This
    turns that from a dead end into one command.
    """
    prov = provider if isinstance(provider, Provider) else resolve_provider(provider)
    url = (os.environ.get(BASE_URL_OVERRIDE) or prov.base_url).replace(
        "/chat/completions", "/models"
    )
    headers = {"user-agent": "agentcheck/0.1"}
    if prov.env_key and os.environ.get(prov.env_key):
        headers["authorization"] = f"Bearer {os.environ[prov.env_key]}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise LLMError(
            f"{prov.name} returned HTTP {exc.code}: "
            f"{exc.read().decode('utf-8', 'replace')[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"could not reach {prov.name}: {exc.reason}") from exc
    return sorted(m["id"] for m in body.get("data", []) if "id" in m)
