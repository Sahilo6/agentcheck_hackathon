"""A small MCP client, and a bridge that drives an Agent through one.

Two uses:

  * testing the server through the real wire format rather than by poking at its
    internals, and
  * proving equivalence -- the same agent on the same scenario must produce an
    identical trace whether it runs in-process or over MCP. If those two ever
    diverge, one of the paths is lying, and the MCP route stops being trustworthy.
"""

from __future__ import annotations

import subprocess
from typing import Any, Callable, Protocol

from ..runtime.agent import Agent, FinishAction, Observation, ToolAction
from ..runtime.tools import Toolset
from ..runtime.trace import Trace
from ..spec.models import ScenarioSpec
from . import protocol as rpc
from .server import ScenarioServer


class Transport(Protocol):
    def send(self, message: dict[str, Any]) -> dict[str, Any] | None: ...
    def close(self) -> None: ...


class InProcessTransport:
    """Hands messages straight to a server object.

    Skips the pipe, keeps the message shapes. Used where the test is about
    behaviour rather than framing.
    """

    def __init__(self, server: ScenarioServer) -> None:
        self.server = server

    def send(self, message: dict[str, Any]) -> dict[str, Any] | None:
        return self.server.handle(message)

    def close(self) -> None:
        self.server.finalize()


class StdioTransport:
    """Talks to a server subprocess over its stdin and stdout."""

    def __init__(self, command: list[str]) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def send(self, message: dict[str, Any]) -> dict[str, Any] | None:
        assert self.process.stdin and self.process.stdout
        rpc.write_message(self.process.stdin, message)
        if "id" not in message:
            return None  # notifications get no reply
        return rpc.read_message(self.process.stdout)

    def close(self) -> None:
        if self.process.stdin:
            self.process.stdin.close()
        self.process.wait(timeout=10)


class MCPClient:
    """Enough of an MCP client to complete a handshake and call tools."""

    def __init__(self, transport: Transport, *, name: str = "agentcheck-client") -> None:
        self.transport = transport
        self.name = name
        self._next_id = 0
        self.instructions = ""
        self.tools: list[dict[str, Any]] = []

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        reply = self.transport.send(rpc.request(self._next_id, method, params))
        if reply is None:
            raise RuntimeError(f"no reply to {method}")
        if "error" in reply:
            raise RuntimeError(f"{method} failed: {reply['error']['message']}")
        return reply.get("result", {})

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": rpc.PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": self.name, "version": "0.1.0"},
            },
        )
        self.instructions = result.get("instructions", "")
        self.transport.send(rpc.notification("notifications/initialized"))
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        self.tools = self._request("tools/list").get("tools", [])
        return self.tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        """Call a tool. Returns (ok, text)."""
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        blocks = result.get("content", [])
        text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return not result.get("isError", False), text

    def close(self) -> None:
        self.transport.close()


def run_scenario_over_mcp(
    spec: ScenarioSpec,
    agent: Agent,
    toolset: Toolset,
    *,
    transport_factory: Callable[[ScenarioServer], Transport] | None = None,
) -> Trace:
    """Run one scenario with the agent talking MCP instead of calling in-process.

    The agent's tool manifest comes from `tools/list`, so it sees exactly what any
    third-party MCP client would see, including the injected `finish` tool.
    """
    server = ScenarioServer(spec, toolset, agent_id=getattr(agent, "id", "mcp-client"))
    transport = (transport_factory or InProcessTransport)(server)
    client = MCPClient(transport)

    client.initialize()
    manifest = client.list_tools()
    # Hide `finish` from the agent's manifest: it is harness plumbing, and an
    # agent offered it as a normal tool would call it instead of doing the work.
    visible = [t for t in manifest if t["name"] != "finish"]
    agent.begin(client.instructions or spec.task, [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["inputSchema"],
            "destructive": t.get("annotations", {}).get("destructiveHint", False),
        }
        for t in visible
    ])

    observation: Observation | None = None
    try:
        while True:
            if server.trace.steps_used >= spec.budget.max_steps:
                server.trace.stopped = "budget_steps"
                break
            if len(server.trace.calls) >= spec.budget.max_tool_calls:
                server.trace.stopped = "budget_calls"
                break

            action = agent.step(observation)
            if isinstance(action, FinishAction):
                client.call_tool("finish", {"summary": action.message})
                break
            if not isinstance(action, ToolAction):
                server.trace.stopped = "error"
                server.trace.error = f"agent returned {type(action).__name__}"
                break

            ok, text = client.call_tool(action.tool, action.args)
            observation = Observation(tool=action.tool, ok=ok, result=text)
    except Exception as exc:
        server.trace.stopped = "error"
        server.trace.error = f"{type(exc).__name__}: {exc}"

    trace = server.finalize()
    client.close()
    return trace
