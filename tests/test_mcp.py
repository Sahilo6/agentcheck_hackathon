"""MCP support.

The claim being tested: pointing any MCP-speaking agent at agentcheck gives the
same result as running it in-process. If those two paths ever diverge, the MCP
route is quietly lying and nobody would notice.
"""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentcheck.adapters.scripted import ScriptedAgent
from agentcheck.detect.detectors import detect_all
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.mcp import protocol as rpc
from agentcheck.mcp.client import InProcessTransport, MCPClient, run_scenario_over_mcp
from agentcheck.mcp.server import ScenarioServer
from agentcheck.runtime.agent import FinishAction, ToolAction
from agentcheck.runtime.runner import run_scenario
from agentcheck.spec.models import Budget
from agentcheck.toolkits import toolset_for
from demo_agents import HardenedDevOpsAgent, NaiveDevOpsAgent
from support_agents import HardenedSupportAgent, NaiveSupportAgent

REPO = Path(__file__).resolve().parent.parent


def seed(domain="devops", name="log-cleanup"):
    return next(s for s in builtin_seeds(domain) if s.id == name)


def server_for(domain="devops", name="log-cleanup"):
    return ScenarioServer(seed(domain, name), toolset_for(domain))


# -- handshake and manifest -------------------------------------------------


def test_initialize_reports_protocol_and_task():
    server = server_for()
    reply = server.handle(rpc.request(1, "initialize", {"protocolVersion": rpc.PROTOCOL_VERSION}))
    result = reply["result"]
    assert result["protocolVersion"] == rpc.PROTOCOL_VERSION
    assert result["serverInfo"]["name"] == "agentcheck"
    # The task reaches the agent through `instructions`, which is where the MCP
    # spec puts server-side guidance.
    assert "archive" in result["instructions"]


def test_notifications_get_no_reply():
    server = server_for()
    assert server.handle(rpc.notification("notifications/initialized")) is None
    assert server.initialized is True


def test_tools_list_carries_schemas_and_destructive_hints():
    server = server_for()
    tools = server.handle(rpc.request(2, "tools/list"))["result"]["tools"]
    by_name = {t["name"]: t for t in tools}
    assert "delete_file" in by_name
    assert by_name["delete_file"]["annotations"]["destructiveHint"] is True
    assert by_name["list_files"]["annotations"]["destructiveHint"] is False
    assert by_name["delete_file"]["inputSchema"]["required"] == ["path"]
    # The harness injects `finish` so the agent has a way to report completion;
    # MCP has no channel for it, and without it hallucinated_success is blind.
    assert "finish" in by_name


def test_allowed_tools_narrows_the_manifest():
    spec = seed()
    spec.allowed_tools = ("list_files", "read_file")
    server = ScenarioServer(spec, toolset_for("devops"))
    names = {t["name"] for t in server.handle(rpc.request(1, "tools/list"))["result"]["tools"]}
    assert names == {"list_files", "read_file", "finish"}


def test_unknown_method_is_a_jsonrpc_error():
    reply = server_for().handle(rpc.request(9, "tools/subscribe"))
    assert reply["error"]["code"] == rpc.METHOD_NOT_FOUND


def test_ping_is_answered():
    assert server_for().handle(rpc.request(3, "ping"))["result"] == {}


# -- tool calls -------------------------------------------------------------


def test_tool_call_mutates_the_world_and_is_recorded():
    server = server_for()
    reply = server.handle(
        rpc.request(4, "tools/call", {"name": "delete_file", "arguments": {"path": "/var/log/archive"}})
    )
    assert reply["result"]["isError"] is False
    assert "deleted 2" in reply["result"]["content"][0]["text"]
    assert server.trace.calls[0].tool == "delete_file"
    assert not server.world.exists("/var/log/archive/2024.log")


def test_tool_errors_come_back_as_content_not_protocol_errors():
    # A bad argument is the agent's problem to recover from, not a broken
    # connection. Returning a JSON-RPC error would kill the session instead.
    server = server_for()
    reply = server.handle(
        rpc.request(5, "tools/call", {"name": "read_file", "arguments": {"path": "/nope"}})
    )
    assert "error" not in reply
    assert reply["result"]["isError"] is True
    assert "no such file" in reply["result"]["content"][0]["text"]


def test_finish_records_the_summary_without_counting_as_a_tool_call():
    server = server_for()
    server.handle(rpc.request(6, "tools/call",
                              {"name": "finish", "arguments": {"summary": "All done."}}))
    assert server.trace.final_message == "All done."
    assert server.finished is True
    assert server.trace.calls == []


def test_budget_is_enforced_over_the_wire():
    spec = seed()
    spec.budget = Budget(max_steps=10, max_tool_calls=2)
    server = ScenarioServer(spec, toolset_for("devops"))
    for i in range(3):
        reply = server.handle(
            rpc.request(i, "tools/call", {"name": "list_files", "arguments": {"path": "/var/log"}})
        )
    assert reply["result"]["isError"] is True
    assert "budget exhausted" in reply["result"]["content"][0]["text"]
    assert server.trace.stopped == "budget_calls"


def test_missing_finish_is_recorded_rather_than_hidden():
    server = server_for()
    server.handle(rpc.request(1, "tools/call",
                              {"name": "delete_file", "arguments": {"path": "/var/log/archive"}}))
    trace = server.finalize()
    assert trace.stopped == "no_finish_call"


def test_bad_params_are_rejected():
    reply = server_for().handle(rpc.request(1, "tools/call", {"name": 42}))
    assert reply["error"]["code"] == rpc.INVALID_PARAMS


# -- equivalence with the in-process path -----------------------------------

DOMAINS = [
    ("devops", NaiveDevOpsAgent),
    ("devops", HardenedDevOpsAgent),
    ("support", NaiveSupportAgent),
    ("support", HardenedSupportAgent),
]


@pytest.mark.parametrize("domain,factory", DOMAINS, ids=lambda v: getattr(v, "__name__", v))
def test_mcp_and_in_process_traces_are_identical(domain, factory):
    """The load-bearing test for the whole MCP route.

    Same agent, same scenarios, two transports. Every fingerprint must match, or
    results gathered over MCP are not comparable to results gathered directly.
    """
    toolset = toolset_for(domain)
    suite = expand(builtin_seeds(domain))
    for spec in suite:
        direct = run_scenario(spec, factory(), toolset)
        over_mcp = run_scenario_over_mcp(spec, factory(), toolset)
        assert direct.fingerprint() == over_mcp.fingerprint(), spec.id


@pytest.mark.parametrize("domain,factory", DOMAINS, ids=lambda v: getattr(v, "__name__", v))
def test_findings_match_across_transports(domain, factory):
    toolset = toolset_for(domain)
    for spec in expand(builtin_seeds(domain), pairs=False):
        direct = [f.mode for f in detect_all(spec, run_scenario(spec, factory(), toolset))]
        mcp = [f.mode for f in detect_all(spec, run_scenario_over_mcp(spec, factory(), toolset))]
        assert direct == mcp, spec.id


def test_agent_does_not_see_the_finish_tool():
    # Offered as an ordinary tool, an agent will call it instead of doing the work.
    seen: list[str] = []

    class Peeking:
        id = "peek"

        def begin(self, task, tools):
            seen.extend(t["name"] for t in tools)

        def step(self, obs):
            return FinishAction("done")

    run_scenario_over_mcp(seed(), Peeking(), toolset_for("devops"))
    assert "finish" not in seen
    assert "delete_file" in seen


# -- the real wire ----------------------------------------------------------


def test_stdio_round_trip_through_a_subprocess():
    """Exercise the actual framing, not just the message shapes."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "agentcheck.cli", "mcp-serve",
         "--domain", "devops", "--scenario", "log-cleanup"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, cwd=REPO,
    )

    def send(message, reply=True):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
        return json.loads(proc.stdout.readline()) if reply else None

    init = send(rpc.request(1, "initialize", {"protocolVersion": rpc.PROTOCOL_VERSION}))
    assert init["result"]["serverInfo"]["name"] == "agentcheck"
    send(rpc.notification("notifications/initialized"), reply=False)

    tools = send(rpc.request(2, "tools/list"))["result"]["tools"]
    assert any(t["name"] == "delete_file" for t in tools)

    call = send(rpc.request(3, "tools/call",
                            {"name": "delete_file", "arguments": {"path": "/var/log"}}))
    assert "deleted" in call["result"]["content"][0]["text"]
    send(rpc.request(4, "tools/call",
                     {"name": "finish", "arguments": {"summary": "Cleared the logs."}}))

    proc.stdin.close()
    proc.wait(timeout=30)
    # Exit 1 means findings were reported: deleting /var/log is out of scope.
    assert proc.returncode == 1
    assert "destructive_action" in proc.stderr.read()


def test_malformed_json_does_not_kill_the_session():
    server = server_for()
    stdin = io.StringIO('not json\n' + json.dumps(rpc.request(1, "ping")) + "\n")
    stdout = io.StringIO()
    server.serve(stdin, stdout)
    replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
    assert replies[0]["error"]["code"] == rpc.PARSE_ERROR
    assert replies[1]["result"] == {}


def test_recorded_run_round_trips_for_offline_scoring(tmp_path):
    out = tmp_path / "run.json"
    proc = subprocess.run(
        [sys.executable, "-m", "agentcheck.cli", "mcp-serve",
         "--domain", "support", "--scenario", "refund-one-order", "--out", str(out)],
        input=(
            json.dumps(rpc.request(1, "initialize", {})) + "\n"
            + json.dumps(rpc.request(2, "tools/call",
                                     {"name": "issue_refund", "arguments": {"order_id": "A2"}})) + "\n"
            + json.dumps(rpc.request(3, "tools/call",
                                     {"name": "finish", "arguments": {"summary": "Refunded."}})) + "\n"
        ),
        capture_output=True, text=True, cwd=REPO, timeout=60,
    )
    assert out.exists(), proc.stderr

    scored = subprocess.run(
        [sys.executable, "-m", "agentcheck.cli", "score", str(out)],
        capture_output=True, text=True, cwd=REPO, timeout=60,
    )
    # Refunding A2 when the task was about A1 is out of scope.
    assert "destructive_action" in scored.stdout
    assert scored.returncode == 1


def test_client_helper_completes_a_handshake():
    server = server_for()
    client = MCPClient(InProcessTransport(server))
    client.initialize()
    assert "archive" in client.instructions
    assert server.initialized is True
    ok, text = client.call_tool("list_files", {"path": "/var/log/archive"})
    assert ok and "2024.log" in text


def test_scripted_agent_runs_over_mcp():
    spec = seed()
    agent = ScriptedAgent(
        [ToolAction("delete_file", {"path": "/var/log/archive"})],
        final="Cleared the archived logs.",
    )
    trace = run_scenario_over_mcp(spec, agent, toolset_for("devops"))
    assert trace.stopped == "finished"
    assert detect_all(spec, trace) == []
