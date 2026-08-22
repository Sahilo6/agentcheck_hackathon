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
import urllib.error
import urllib.request
from dataclasses import dataclass


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


PROVIDERS: dict[str, Provider] = {
    "groq": Provider(
        "groq",
        "https://api.groq.com/openai/v1/chat/completions",
        "GROQ_API_KEY",
        "llama-3.3-70b-versatile",
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

FREE_OPTIONS = """No LLM provider configured. Scenario generation needs one
(everything else in agentcheck runs without a model).

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


def chat(
    messages: list[dict[str, str]],
    *,
    provider: str | Provider | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 8000,
    timeout: int = 120,
) -> str:
    """Send a chat completion request and return the assistant's text.

    Temperature defaults to 0: generation is cached, and a cache whose contents
    shift between fills is not much of a cache.
    """
    prov = provider if isinstance(provider, Provider) else resolve_provider(provider)

    headers = {"content-type": "application/json"}
    if prov.env_key:
        key = os.environ.get(prov.env_key)
        if not key:
            raise MissingAPIKeyError(
                f"{prov.name} selected but {prov.env_key} is not set.\n\n{FREE_OPTIONS}"
            )
        headers["authorization"] = f"Bearer {key}"

    # Several providers sit behind Cloudflare, which 403s the default
    # "Python-urllib/3.x" user agent outright. Identifying ourselves avoids a
    # confusing failure that looks like a bad API key.
    headers["user-agent"] = "agentcheck/0.1"

    payload = {
        "model": model or prov.default_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        prov.base_url, data=json.dumps(payload).encode("utf-8"), headers=headers
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Surface the response body: providers explain quota and model errors
        # there, and hiding it turns a two-second fix into a debugging session.
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise LLMError(f"{prov.name} returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"could not reach {prov.name} at {prov.base_url}: {exc.reason}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape from {prov.name}: {body}") from exc


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
