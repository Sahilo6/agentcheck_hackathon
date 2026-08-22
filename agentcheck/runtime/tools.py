"""Tool definitions and the dispatcher that binds them to a mock world.

A `ToolDef` carries the JSON Schema the scenario generator reads, the
`destructive` flag the guardrail detector reads, and the handler that applies
the call to the world. One declaration, three consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..world.mock import MockWorld, WorldError

Handler = Callable[[MockWorld, dict[str, Any]], str]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema (object)
    handler: Handler
    # Marks a tool whose effects cannot be undone. Calling one of these outside
    # a scenario's allowed set is a classified failure, not a style complaint.
    destructive: bool = False

    def required(self) -> list[str]:
        return list(self.parameters.get("required", []))

    def properties(self) -> dict[str, Any]:
        return self.parameters.get("properties", {})


class SchemaError(Exception):
    """Raised when a tool call does not satisfy the tool's declared schema."""


_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


def validate_args(tool: ToolDef, args: dict[str, Any]) -> None:
    """Minimal JSON-Schema check.

    Deliberately hand-rolled rather than pulling in `jsonschema`: the core stays
    dependency-free, and we only need the subset that tool schemas actually use.
    Schema violations are a *reported failure mode*, so this must not be lenient.
    """
    if not isinstance(args, dict):
        raise SchemaError(f"{tool.name}: arguments must be an object, got {type(args).__name__}")

    props = tool.properties()
    for name in tool.required():
        if name not in args:
            raise SchemaError(f"{tool.name}: missing required argument {name!r}")

    for key, value in args.items():
        if key not in props:
            raise SchemaError(f"{tool.name}: unexpected argument {key!r}")
        expected = props[key].get("type")
        if expected is None:
            continue
        allowed = _TYPE_MAP.get(expected)
        if allowed is None:
            continue
        # bool is a subclass of int in Python; reject it for numeric fields so
        # `count=True` is caught rather than silently treated as 1.
        if expected in ("integer", "number") and isinstance(value, bool):
            raise SchemaError(f"{tool.name}: {key!r} must be {expected}, got boolean")
        if not isinstance(value, allowed):
            raise SchemaError(
                f"{tool.name}: {key!r} must be {expected}, got {type(value).__name__}"
            )
        enum = props[key].get("enum")
        if enum is not None and value not in enum:
            raise SchemaError(f"{tool.name}: {key!r} must be one of {enum}, got {value!r}")


class Toolset:
    """A named collection of tools bound to a world instance."""

    def __init__(self, name: str, tools: list[ToolDef]) -> None:
        self.name = name
        self._tools = {t.name: t for t in tools}

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __iter__(self):
        return iter(self._tools.values())

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def destructive_names(self) -> list[str]:
        return sorted(t.name for t in self._tools.values() if t.destructive)

    def schemas(self) -> list[dict[str, Any]]:
        """The tool manifest handed to an agent, and read by the generator."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "destructive": t.destructive,
            }
            for t in sorted(self._tools.values(), key=lambda t: t.name)
        ]

    def invoke(self, world: MockWorld, name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Run a tool call against the world.

        Returns (ok, rendered_result). Failures are returned rather than raised:
        an agent that mis-calls a tool should see the error and get the chance to
        recover, exactly as it would in production. How it responds is itself
        signal we want in the trace.
        """
        tool = self._tools.get(name)
        if tool is None:
            return False, f"error: no such tool {name!r}"
        try:
            validate_args(tool, args)
        except SchemaError as exc:
            return False, f"error: {exc}"
        try:
            return True, tool.handler(world, args)
        except WorldError as exc:
            return False, f"error: {exc}"
        except Exception as exc:  # a broken handler must not kill the whole run
            return False, f"error: tool crashed: {exc}"


def render_manifest(toolset: Toolset) -> str:
    """A compact text manifest for prompting an LLM-backed agent."""
    lines = []
    for t in sorted(toolset, key=lambda t: t.name):
        params = ", ".join(
            f"{k}: {v.get('type', 'any')}" for k, v in t.properties().items()
        )
        flag = "  [DESTRUCTIVE]" if t.destructive else ""
        lines.append(f"- {t.name}({params}) -- {t.description}{flag}")
    return "\n".join(lines)
