"""Minimal JSON-RPC 2.0 framing for MCP over stdio.

Hand-rolled rather than taking the MCP SDK as a dependency: the core of
agentcheck installs with nothing, and the wire format here is a few hundred
bytes of newline-delimited JSON. Taking a dependency to write four message
shapes would be a poor trade for a tool meant to run in CI.
"""

from __future__ import annotations

import json
from typing import Any, IO

# The revision of the MCP spec these messages target.
PROTOCOL_VERSION = "2025-06-18"

# JSON-RPC error codes we actually emit.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def request(request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


def notification(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        message["params"] = params
    return message


def result(request_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def write_message(stream: IO[str], message: dict[str, Any]) -> None:
    """Write one message as a single line, then flush.

    Flushing matters: the peer is usually blocked on readline, and a buffered
    reply deadlocks both sides.
    """
    stream.write(json.dumps(message, separators=(",", ":")) + "\n")
    stream.flush()


def read_message(stream: IO[str]) -> dict[str, Any] | None:
    """Read one message, skipping blank lines. None at end of stream."""
    while True:
        line = stream.readline()
        if line == "":
            return None
        line = line.strip()
        if line:
            return json.loads(line)


def text_content(text: str, *, is_error: bool = False) -> dict[str, Any]:
    """A tools/call result in MCP's content-block shape."""
    return {"content": [{"type": "text", "text": text}], "isError": is_error}
