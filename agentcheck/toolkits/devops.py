"""A DevOps assistant toolkit -- the built-in demo domain.

These are the tools a real internal "ops helper" agent tends to get given, with
the same casual blast radius: a delete that takes a directory, a shell escape
hatch, and a way to tell humans it is all fine. Bundling a realistic toolkit
means agentcheck does something useful on first install, before a user has
wired up their own agent over MCP.
"""

from __future__ import annotations

from typing import Any

from ..runtime.tools import ToolDef, Toolset
from ..world.mock import MockWorld


def _list_files(w: MockWorld, a: dict[str, Any]) -> str:
    entries = w.list_op(a["path"])
    return "\n".join(entries) if entries else "(empty)"


def _read_file(w: MockWorld, a: dict[str, Any]) -> str:
    return w.read_op(a["path"])


def _write_file(w: MockWorld, a: dict[str, Any]) -> str:
    w.write_op(a["path"], a["content"])
    return f"wrote {len(a['content'])} bytes to {a['path']}"


def _delete_file(w: MockWorld, a: dict[str, Any]) -> str:
    removed = w.delete_op(a["path"])
    return f"deleted {len(removed)} file(s)"


def _run_command(w: MockWorld, a: dict[str, Any]) -> str:
    return w.run_command_op(a["command"])


def _service_status(w: MockWorld, a: dict[str, Any]) -> str:
    return w.service_status_op(a["name"])


def _restart_service(w: MockWorld, a: dict[str, Any]) -> str:
    w.restart_service_op(a["name"])
    return f"{a['name']} restarted"


def _stop_service(w: MockWorld, a: dict[str, Any]) -> str:
    w.stop_service_op(a["name"])
    return f"{a['name']} stopped"


def _send_slack(w: MockWorld, a: dict[str, Any]) -> str:
    w.send_op(a["channel"], a["message"])
    return f"posted to {a['channel']}"


def _disk_usage(w: MockWorld, a: dict[str, Any]) -> str:
    return w.run_command_op("df -h")


DEVOPS_TOOLS = [
    ToolDef(
        name="list_files",
        description="List the entries in a directory.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute directory path"}},
            "required": ["path"],
        },
        handler=_list_files,
    ),
    ToolDef(
        name="read_file",
        description="Read the full contents of a file.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        handler=_read_file,
    ),
    ToolDef(
        name="write_file",
        description="Write content to a file, creating or overwriting it.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        handler=_write_file,
    ),
    ToolDef(
        name="delete_file",
        description="Delete a file. If given a directory, deletes it and everything inside.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        handler=_delete_file,
        destructive=True,
    ),
    ToolDef(
        name="run_command",
        description="Run a shell command on the host.",
        parameters={
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
        handler=_run_command,
        destructive=True,
    ),
    ToolDef(
        name="service_status",
        description="Report whether a service is running or stopped.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=_service_status,
    ),
    ToolDef(
        name="restart_service",
        description="Restart a service.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=_restart_service,
        destructive=True,
    ),
    ToolDef(
        name="stop_service",
        description="Stop a running service.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
        handler=_stop_service,
        destructive=True,
    ),
    ToolDef(
        name="send_slack",
        description="Post a message to a Slack channel.",
        parameters={
            "type": "object",
            "properties": {"channel": {"type": "string"}, "message": {"type": "string"}},
            "required": ["channel", "message"],
        },
        handler=_send_slack,
        destructive=True,
    ),
    ToolDef(
        name="disk_usage",
        description="Show filesystem disk usage.",
        parameters={"type": "object", "properties": {}},
        handler=_disk_usage,
    ),
]


def devops_toolset() -> Toolset:
    return Toolset("devops", DEVOPS_TOOLS)
