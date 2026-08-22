"""Trace determinism.

The regression story rests entirely on this: if two runs of the same scenario do
not produce the same fingerprint, then a "new failure" in the diff might just be
sampling noise, and the whole tool is theatre.
"""

from agentcheck.runtime.trace import Trace


def build(final="done", args=None):
    t = Trace(scenario_id="s1", agent_id="devops-v1")
    t.add_call("list_files", args or {"path": "/var/log"}, ok=True, result="app.log")
    t.add_call("delete_file", {"path": "/var/log/old"}, ok=True, result="removed 2")
    t.final_message = final
    t.world_after = {"files": {"/var/log/app.log": "x"}}
    return t


def test_identical_runs_share_a_fingerprint():
    assert build().fingerprint() == build().fingerprint()


def test_different_final_message_changes_fingerprint():
    assert build(final="done").fingerprint() != build(final="all clear").fingerprint()


def test_different_tool_args_change_fingerprint():
    a = build(args={"path": "/var/log"})
    b = build(args={"path": "/etc"})
    assert a.fingerprint() != b.fingerprint()


def test_fingerprint_ignores_key_order_in_args():
    t1 = Trace(scenario_id="s", agent_id="a")
    t1.add_call("write_file", {"path": "/a", "content": "x"}, ok=True, result="ok")
    t2 = Trace(scenario_id="s", agent_id="a")
    t2.add_call("write_file", {"content": "x", "path": "/a"}, ok=True, result="ok")
    assert t1.fingerprint() == t2.fingerprint()


def test_call_signature_is_stable_for_the_loop_detector():
    t = build()
    first = t.calls[0].signature()
    assert first == "list_files({\"path\":\"/var/log\"})"
    # Same call made again must produce the identical signature, which is how
    # repetition is counted.
    t.add_call("list_files", {"path": "/var/log"}, ok=True, result="app.log")
    assert t.calls[-1].signature() == first


def test_round_trip_through_dict_preserves_fingerprint():
    original = build()
    restored = Trace.from_dict(original.to_dict())
    assert restored.fingerprint() == original.fingerprint()


def test_trace_queries():
    t = build()
    assert t.called("delete_file") is True
    assert t.called("run_command") is False
    assert t.tools_used() == ["list_files", "delete_file"]
    assert len(t.calls_to("delete_file")) == 1
