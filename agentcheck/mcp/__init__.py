"""MCP support: expose a scenario's mock world to any MCP-speaking agent."""

from .client import MCPClient, run_scenario_over_mcp
from .server import ScenarioServer

__all__ = ["MCPClient", "ScenarioServer", "run_scenario_over_mcp"]
