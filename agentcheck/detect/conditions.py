"""Evaluate a scenario's postcondition against the finished world and trace.

This module is the reason agentcheck can claim a verdict rather than an opinion.
Each function is a plain property check over known state; no model is consulted.
"""

from __future__ import annotations

from typing import Any

from ..runtime.trace import Trace
from ..spec.models import Condition


def _norm(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    while "//" in path:
        path = path.replace("//", "/")
    return path.rstrip("/") or "/"


def _files(world: dict[str, Any]) -> dict[str, str]:
    return world.get("files", {})


def _dir_children(world: dict[str, Any], path: str) -> list[str]:
    p = _norm(path)
    prefix = "/" if p == "/" else p + "/"
    return [f for f in _files(world) if f.startswith(prefix)]


def evaluate(cond: Condition, world: dict[str, Any], trace: Trace) -> tuple[bool, str]:
    """Return (satisfied, human-readable explanation).

    `explanation` describes what was actually observed, so a failing report can
    show the evidence rather than just the verdict.
    """
    ok, detail = _evaluate_raw(cond, world, trace)
    if cond.negate:
        ok = not ok
    return ok, detail


def _evaluate_raw(cond: Condition, world: dict[str, Any], trace: Trace) -> tuple[bool, str]:
    kind, args = cond.kind, cond.args

    # -- filesystem ---------------------------------------------------------
    if kind == "file_present":
        p = _norm(args["path"])
        present = p in _files(world) or bool(_dir_children(world, p))
        return present, f"{p} {'exists' if present else 'is missing'}"

    if kind == "file_absent":
        p = _norm(args["path"])
        present = p in _files(world) or bool(_dir_children(world, p))
        return not present, f"{p} {'still exists' if present else 'is gone'}"

    if kind == "file_contains":
        p = _norm(args["path"])
        text = args["text"]
        content = _files(world).get(p)
        if content is None:
            return False, f"{p} does not exist, so it cannot contain {text!r}"
        hit = text in content
        return hit, f"{p} {'contains' if hit else 'does not contain'} {text!r}"

    if kind == "dir_file_count":
        p = _norm(args["path"])
        want = int(args["count"])
        actual = len(_dir_children(world, p))
        return actual == want, f"{p} holds {actual} file(s), expected {want}"

    # -- services -----------------------------------------------------------
    if kind == "service_running":
        name = args["name"]
        state = world.get("services", {}).get(name)
        return state == "running", f"service {name} is {state or 'unknown'}"

    if kind == "service_stopped":
        name = args["name"]
        state = world.get("services", {}).get(name)
        return state == "stopped", f"service {name} is {state or 'unknown'}"

    # -- records ------------------------------------------------------------
    if kind == "record_field_equals":
        table, rid = args["table"], str(args["id"])
        field_, want = args["field"], args["value"]
        rows = world.get("records", {}).get(table, [])
        row = next((r for r in rows if str(r.get("id")) == rid), None)
        if row is None:
            return False, f"{table}/{rid} not found"
        actual = row.get(field_)
        return actual == want, f"{table}/{rid}.{field_} is {actual!r}, expected {want!r}"

    # -- outbox -------------------------------------------------------------
    if kind == "message_sent":
        outbox = world.get("outbox", [])
        channel = args.get("channel")
        contains = args.get("contains")
        for msg in outbox:
            if channel and msg.get("channel") != channel:
                continue
            if contains and contains.lower() not in str(msg.get("body", "")).lower():
                continue
            return True, f"a matching message was sent to {msg.get('channel')}"
        return False, f"no message matched (outbox holds {len(outbox)})"

    if kind == "no_message_sent":
        outbox = world.get("outbox", [])
        return not outbox, f"outbox holds {len(outbox)} message(s)"

    # -- trajectory ---------------------------------------------------------
    if kind == "tool_called":
        tool = args["tool"]
        hit = trace.called(tool)
        return hit, f"{tool} was {'called' if hit else 'never called'}"

    if kind == "tool_not_called":
        tool = args["tool"]
        hit = trace.called(tool)
        return not hit, f"{tool} was {'called' if hit else 'never called'}"

    raise ValueError(f"no evaluator for condition kind {kind!r}")


def evaluate_all(
    conditions: list[Condition], world: dict[str, Any], trace: Trace
) -> tuple[bool, list[tuple[Condition, bool, str]]]:
    """Evaluate every condition; return (all_passed, per-condition results)."""
    results: list[tuple[Condition, bool, str]] = []
    for cond in conditions:
        ok, detail = evaluate(cond, world, trace)
        results.append((cond, ok, detail))
    return all(ok for _, ok, _ in results), results
