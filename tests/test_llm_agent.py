"""The real-LLM adapter, exercised against a stubbed provider.

No network and no API key: the provider call is the only thing stubbed, so the
tool loop, argument parsing, history construction, and fallback path all run for
real. That keeps the adapter covered on a machine with no credentials, which is
most machines.
"""

import json

import pytest

from agentcheck.adapters.llm_agent import LLMAgent
from agentcheck.detect.detectors import detect_all
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.llm import LLMError
from agentcheck.runtime.agent import FinishAction, ToolAction
from agentcheck.runtime.runner import run_scenario
from agentcheck.toolkits import toolset_for

TOOLS = toolset_for("devops")


def seed(name="log-cleanup"):
    return next(s for s in builtin_seeds("devops") if s.id == name)


def tool_call(name, args, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ],
    }


def text(content):
    return {"role": "assistant", "content": content}


class Stub:
    """Returns queued messages, and records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls: list[dict] = []

    def __call__(self, messages, **kwargs):
        self.calls.append({"messages": [dict(m) for m in messages], **kwargs})
        return self.replies.pop(0) if self.replies else text("Done.")


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-real")

    def build(*replies):
        stub = Stub(*replies)
        monkeypatch.setattr("agentcheck.adapters.llm_agent.chat_message", stub)
        return LLMAgent(provider="groq", model="stub-model"), stub

    return build


# -- identity and setup -----------------------------------------------------


def test_agent_id_names_provider_and_model(agent):
    a, _ = agent()
    assert a.id == "llm:groq:stub-model"


def test_missing_api_key_fails_immediately(monkeypatch):
    # Better to fail before the first scenario than after a hundred.
    for key in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("AGENTCHECK_LLM_PROVIDER", raising=False)
    with pytest.raises(Exception) as exc:
        LLMAgent()
    assert "provider" in str(exc.value).lower()


def test_tools_are_sent_in_openai_function_shape(agent):
    a, stub = agent(text("Nothing to do."))
    spec = seed()
    run_scenario(spec, a, TOOLS)
    sent = stub.calls[0]["tools"]
    names = {t["function"]["name"] for t in sent}
    assert "delete_file" in names
    assert all(t["type"] == "function" for t in sent)
    assert sent[0]["function"]["parameters"]["type"] == "object"


def test_task_is_the_user_turn(agent):
    a, stub = agent(text("done"))
    run_scenario(seed(), a, TOOLS)
    messages = stub.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "archive" in messages[1]["content"]


# -- the tool loop ----------------------------------------------------------


def test_native_tool_call_is_executed(agent):
    spec = seed()
    a, stub = agent(
        tool_call("delete_file", {"path": "/var/log/archive"}),
        text("Cleared the archived logs."),
    )
    trace = run_scenario(spec, a, TOOLS)
    assert [c.tool for c in trace.calls] == ["delete_file"]
    assert trace.final_message == "Cleared the archived logs."
    assert detect_all(spec, trace) == []


def test_tool_results_come_back_as_tool_role_messages(agent):
    a, stub = agent(
        tool_call("list_files", {"path": "/var/log/archive"}),
        text("Found two files."),
    )
    run_scenario(seed(), a, TOOLS)
    second = stub.calls[1]["messages"]
    tool_msg = next(m for m in second if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_1"
    assert "2024.log" in tool_msg["content"]


def test_malformed_tool_arguments_become_a_schema_violation(agent):
    # The model's mistake must reach the toolset, not be silently repaired.
    spec = seed()
    broken = tool_call("delete_file", {})
    broken["tool_calls"][0]["function"]["arguments"] = "{not json"
    a, _ = agent(broken, text("Tried my best."))
    trace = run_scenario(spec, a, TOOLS)
    assert trace.calls[0].ok is False
    assert "schema_violation" in {f.mode for f in detect_all(spec, trace)}


def test_a_destructive_model_is_caught(agent):
    spec = seed()
    a, _ = agent(
        tool_call("delete_file", {"path": "/var/log"}),
        text("Cleared the logs and restarted the api service."),
    )
    trace = run_scenario(spec, a, TOOLS)
    modes = {f.mode for f in detect_all(spec, trace)}
    assert "destructive_action" in modes
    assert "hallucinated_success" in modes


# -- fallback for models that ignore the tools parameter -------------------


def test_json_action_fallback(agent):
    a, _ = agent(
        text('{"tool": "delete_file", "args": {"path": "/var/log/archive"}}'),
        text('{"done": true, "summary": "Cleared the archive."}'),
    )
    spec = seed()
    trace = run_scenario(spec, a, TOOLS)
    assert [c.tool for c in trace.calls] == ["delete_file"]
    assert trace.final_message == "Cleared the archive."
    assert a.used_json_fallback is True


def test_fallback_result_is_fed_back_without_a_tool_call_id(agent):
    # A `tool` role message with no matching tool_calls turn is rejected by
    # providers, so the fallback path has to use a user turn instead.
    a, stub = agent(
        text('{"tool": "list_files", "args": {"path": "/var/log"}}'),
        text("all good"),
    )
    run_scenario(seed(), a, TOOLS)
    roles = [m["role"] for m in stub.calls[1]["messages"]]
    assert "tool" not in roles
    assert roles.count("user") == 2


def test_prose_without_json_is_treated_as_finishing(agent):
    a, _ = agent(text("I had a look and there was nothing that needed clearing."))
    trace = run_scenario(seed(), a, TOOLS)
    assert trace.calls == []
    assert "nothing that needed clearing" in trace.final_message
    assert a.used_json_fallback is False


def test_fallback_can_be_disabled(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    stub = Stub(text('{"tool": "delete_file", "args": {"path": "/var/log"}}'))
    monkeypatch.setattr("agentcheck.adapters.llm_agent.chat_message", stub)
    a = LLMAgent(provider="groq", allow_json_fallback=False)
    trace = run_scenario(seed(), a, TOOLS)
    # Treated as a final answer rather than an action.
    assert trace.calls == []
    assert "delete_file" in trace.final_message


# -- provider failures ------------------------------------------------------


def test_provider_error_ends_the_run_without_crashing_the_suite(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")

    def boom(messages, **kwargs):
        raise LLMError("429 rate limit exceeded")

    monkeypatch.setattr("agentcheck.adapters.llm_agent.chat_message", boom)
    a = LLMAgent(provider="groq")
    trace = run_scenario(seed(), a, TOOLS)
    assert trace.stopped == "finished"
    assert "provider error" in trace.final_message
    assert a.last_error is not None


# -- history trimming -------------------------------------------------------


def test_history_is_trimmed_without_orphaning_a_tool_result(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    replies = [tool_call("list_files", {"path": "/var/log"}, f"c{i}") for i in range(10)]
    stub = Stub(*replies)
    monkeypatch.setattr("agentcheck.adapters.llm_agent.chat_message", stub)
    a = LLMAgent(provider="groq", max_history=6)
    run_scenario(seed(), a, TOOLS)

    for call in stub.calls:
        messages = call["messages"]
        assert messages[0]["role"] == "system"
        # A tool result must never lead the trimmed window.
        assert messages[2]["role"] != "tool" if len(messages) > 2 else True
        assert len(messages) <= 6
