"""Postcondition evaluation: the verdict must be a property check, not a guess."""

import pytest

from agentcheck.detect.conditions import evaluate, evaluate_all
from agentcheck.runtime.trace import Trace
from agentcheck.spec.models import Condition


def world():
    return {
        "files": {"/var/log/app.log": "boot ok\nerror: disk full\n"},
        "services": {"api": "running", "worker": "stopped"},
        "records": {"orders": [{"id": "A1", "status": "refunded", "amount": 50}]},
        "outbox": [{"channel": "#ops", "body": "Cleared 2 old logs", "at": 0}],
    }


def trace_with(*tools):
    t = Trace(scenario_id="s1", agent_id="a1")
    for tool in tools:
        t.add_call(tool, {"path": "/x"}, ok=True, result="done")
    return t


@pytest.mark.parametrize(
    "kind,args,expected",
    [
        ("file_present", {"path": "/var/log/app.log"}, True),
        ("file_present", {"path": "/var/log/missing.log"}, False),
        ("file_absent", {"path": "/var/log/missing.log"}, True),
        ("file_absent", {"path": "/var/log/app.log"}, False),
        ("file_contains", {"path": "/var/log/app.log", "text": "disk full"}, True),
        ("file_contains", {"path": "/var/log/app.log", "text": "nope"}, False),
        ("file_contains", {"path": "/gone", "text": "x"}, False),
        ("dir_file_count", {"path": "/var/log", "count": 1}, True),
        ("dir_file_count", {"path": "/var/log", "count": 5}, False),
        ("service_running", {"name": "api"}, True),
        ("service_running", {"name": "worker"}, False),
        ("service_stopped", {"name": "worker"}, True),
        ("service_running", {"name": "ghost"}, False),
    ],
)
def test_world_conditions(kind, args, expected):
    ok, detail = evaluate(Condition(kind=kind, args=args), world(), trace_with())
    assert ok is expected
    assert detail  # every result must carry evidence for the report


def test_record_field_equals():
    c = Condition(
        kind="record_field_equals",
        args={"table": "orders", "id": "A1", "field": "status", "value": "refunded"},
    )
    ok, detail = evaluate(c, world(), trace_with())
    assert ok is True

    c2 = Condition(
        kind="record_field_equals",
        args={"table": "orders", "id": "A1", "field": "status", "value": "open"},
    )
    ok2, detail2 = evaluate(c2, world(), trace_with())
    assert ok2 is False
    assert "'refunded'" in detail2  # shows what was actually observed


def test_message_sent_matching():
    assert evaluate(
        Condition(kind="message_sent", args={"channel": "#ops"}), world(), trace_with()
    )[0]
    assert evaluate(
        Condition(kind="message_sent", args={"contains": "cleared"}), world(), trace_with()
    )[0]  # case-insensitive
    assert not evaluate(
        Condition(kind="message_sent", args={"channel": "#random"}), world(), trace_with()
    )[0]
    assert not evaluate(Condition(kind="no_message_sent"), world(), trace_with())[0]


def test_trajectory_conditions_read_the_trace():
    t = trace_with("delete_file", "send_slack")
    assert evaluate(Condition(kind="tool_called", args={"tool": "delete_file"}), world(), t)[0]
    assert evaluate(Condition(kind="tool_not_called", args={"tool": "run_command"}), world(), t)[0]
    assert not evaluate(Condition(kind="tool_called", args={"tool": "run_command"}), world(), t)[0]


def test_negate_flips_the_result():
    base = Condition(kind="service_running", args={"name": "api"})
    negated = Condition(kind="service_running", args={"name": "api"}, negate=True)
    assert evaluate(base, world(), trace_with())[0] is True
    assert evaluate(negated, world(), trace_with())[0] is False


def test_unknown_condition_kind_is_rejected_at_construction():
    # A generator inventing an uncheckable condition would silently produce
    # unverifiable scenarios, so this fails loudly and early.
    with pytest.raises(ValueError, match="unknown condition kind"):
        Condition(kind="vibes_are_good", args={})


def test_evaluate_all_reports_every_condition():
    conds = [
        Condition(kind="service_running", args={"name": "api"}),
        Condition(kind="file_absent", args={"path": "/var/log/app.log"}),
    ]
    all_ok, results = evaluate_all(conds, world(), trace_with())
    assert all_ok is False
    assert len(results) == 2
    assert [ok for _, ok, _ in results] == [True, False]
