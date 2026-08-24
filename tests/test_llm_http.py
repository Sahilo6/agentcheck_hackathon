"""The LLM agent over real HTTP, against a local stub endpoint.

The stubbed-function tests cover the agent loop; this covers the wire: request
shape, native tool_calls, header handling, and error surfacing. Together they
mean the only untested thing is the remote provider itself.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from agentcheck.detect.detectors import detect_all
from agentcheck.engine import run_suite
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.llm import BASE_URL_OVERRIDE, LLMError, chat_message
from agentcheck.runtime.runner import run_scenario
from agentcheck.toolkits import toolset_for

TOOLS = toolset_for("devops")


def make_handler(responder, seen):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["content-length"])))
            # Lowercased: urllib sends "User-Agent", and dict() over the
            # handler's headers loses their case-insensitivity.
            seen.append(
                {"body": body, "headers": {k.lower(): v for k, v in self.headers.items()}}
            )
            status, payload = responder(body)
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    return Handler


@pytest.fixture
def endpoint(monkeypatch):
    """Spin up a local OpenAI-compatible endpoint and point agentcheck at it."""
    servers = []

    def start(responder):
        seen: list[dict] = []
        server = HTTPServer(("127.0.0.1", 0), make_handler(responder, seen))
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        host, port = server.server_address
        monkeypatch.setenv(BASE_URL_OVERRIDE, f"http://{host}:{port}/v1/chat/completions")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        return seen

    yield start
    for server in servers:
        server.shutdown()


def message(content=None, tool=None, args=None, call_id="c1"):
    msg = {"role": "assistant", "content": content}
    if tool:
        msg["tool_calls"] = [
            {"id": call_id, "type": "function",
             "function": {"name": tool, "arguments": json.dumps(args or {})}}
        ]
    return {"choices": [{"message": msg, "finish_reason": "stop"}]}


def seed(name="log-cleanup"):
    return next(s for s in builtin_seeds("devops") if s.id == name)


# -- request shape ----------------------------------------------------------


def test_request_carries_tools_and_identifies_itself(endpoint):
    seen = endpoint(lambda body: (200, message(content="nothing to do")))
    chat_message([{"role": "user", "content": "hi"}], provider="groq", model="m",
                 tools=[{"type": "function",
                         "function": {"name": "t", "description": "d", "parameters": {}}}])
    sent = seen[0]
    assert sent["body"]["model"] == "m"
    assert sent["body"]["tool_choice"] == "auto"
    assert sent["body"]["tools"][0]["function"]["name"] == "t"
    # Several providers sit behind Cloudflare, which 403s the default
    # Python-urllib user agent outright.
    assert sent["headers"]["user-agent"] == "agentcheck/0.1"


def test_temperature_defaults_to_zero(endpoint):
    seen = endpoint(lambda body: (200, message(content="ok")))
    chat_message([{"role": "user", "content": "hi"}], provider="groq")
    assert seen[0]["body"]["temperature"] == 0.0


# -- the agent over the wire ------------------------------------------------


def test_agent_completes_a_scenario_over_http(endpoint):
    from agentcheck.adapters.llm_agent import LLMAgent

    def responder(body):
        if any(m["role"] == "tool" for m in body["messages"]):
            return 200, message(content="Cleared the archived logs.")
        return 200, message(tool="delete_file", args={"path": "/var/log/archive"})

    endpoint(responder)
    spec = seed()
    trace = run_scenario(spec, LLMAgent(provider="groq", model="stub"), TOOLS)
    assert [c.tool for c in trace.calls] == ["delete_file"]
    assert detect_all(spec, trace) == []


def test_a_careless_model_is_caught_over_http(endpoint):
    from agentcheck.adapters.llm_agent import LLMAgent

    def responder(body):
        if any(m["role"] == "tool" for m in body["messages"]):
            return 200, message(
                content="Cleared the logs and restarted the api service. All healthy."
            )
        return 200, message(tool="delete_file", args={"path": "/var/log"})

    endpoint(responder)
    spec = seed()
    trace = run_scenario(spec, LLMAgent(provider="groq", model="stub"), TOOLS)
    modes = {f.mode for f in detect_all(spec, trace)}
    assert "destructive_action" in modes
    assert "hallucinated_success" in modes


# -- errors -----------------------------------------------------------------


def test_http_error_body_is_surfaced(endpoint):
    endpoint(lambda body: (429, {"error": {"message": "rate limit reached for llama-3.3"}}))
    with pytest.raises(LLMError) as exc:
        chat_message([{"role": "user", "content": "hi"}], provider="groq")
    # Providers explain quota problems in the body; hiding it turns a
    # two-second fix into a debugging session.
    assert "429" in str(exc.value)
    assert "rate limit reached" in str(exc.value)


def test_unexpected_response_shape_is_reported(endpoint):
    endpoint(lambda body: (200, {"not_choices": []}))
    with pytest.raises(LLMError, match="unexpected response shape"):
        chat_message([{"role": "user", "content": "hi"}], provider="groq")


def test_unreachable_endpoint_names_the_url(monkeypatch):
    monkeypatch.setenv(BASE_URL_OVERRIDE, "http://127.0.0.1:1/v1/chat/completions")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="could not reach"):
        chat_message([{"role": "user", "content": "hi"}], provider="groq")


# -- record now, replay forever --------------------------------------------


def test_llm_run_replays_with_the_endpoint_gone(endpoint, tmp_path):
    """The demo-safety guarantee.

    A run against a real model is recorded once and then replays identically
    with nothing listening, so no live call ever sits on the critical path of a
    presentation.
    """
    from agentcheck.adapters.llm_agent import LLMAgent

    def responder(body):
        if any(m["role"] == "tool" for m in body["messages"]):
            return 200, message(content="Cleared the logs and restarted the api service.")
        return 200, message(tool="delete_file", args={"path": "/var/log"})

    endpoint(responder)
    suite = expand(builtin_seeds("devops"), pairs=False)[:6]
    store = tmp_path / "llm.jsonl"

    live = run_suite(
        suite, lambda: LLMAgent(provider="groq", model="stub"), TOOLS, record_to=store
    )

    # Break the endpoint entirely, then replay.
    import os
    os.environ[BASE_URL_OVERRIDE] = "http://127.0.0.1:1/nope"
    replayed = run_suite(suite, None, TOOLS, replay_from=store)

    assert replayed.pass_rate == live.pass_rate
    assert replayed.by_mode() == live.by_mode()
    assert replayed.agent_id == live.agent_id
