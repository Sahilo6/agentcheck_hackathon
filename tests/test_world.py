"""The mock world must be exact: every detector downstream trusts its journal."""

import pytest

from agentcheck.world import MockWorld
from agentcheck.world.mock import WorldError


def make_world() -> MockWorld:
    return MockWorld(
        files={
            "/var/log/app.log": "boot ok\n",
            "/var/log/old/2025.log": "archive\n",
            "/var/log/old/2024.log": "archive\n",
            "/etc/app/config.yml": "port: 8080\n",
        },
        services={"api": "running", "worker": "stopped"},
        records={"orders": [{"id": "A1", "status": "open", "amount": 50}]},
        http={"https://status.internal/health": "ok"},
    )


def test_read_and_list():
    w = make_world()
    assert w.read_op("/var/log/app.log") == "boot ok\n"
    assert w.list_op("/var/log") == ["app.log", "old"]
    assert w.list_op("/var/log/old") == ["2024.log", "2025.log"]


def test_read_missing_raises():
    w = make_world()
    with pytest.raises(WorldError):
        w.read_op("/nope.txt")


def test_delete_single_file_records_blast_radius():
    w = make_world()
    removed = w.delete_op("/var/log/app.log")
    assert removed == ["/var/log/app.log"]
    assert not w.exists("/var/log/app.log")
    event = w.journal[-1]
    assert event.op == "delete_file"
    assert event.destructive is True
    assert event.detail["count"] == 1


def test_delete_directory_is_recursive_and_journaled():
    # This is the mechanism behind the demo's headline failure: an agent under
    # time pressure deleting a whole tree instead of the one file it meant to.
    w = make_world()
    removed = w.delete_op("/var/log/old")
    assert removed == ["/var/log/old/2024.log", "/var/log/old/2025.log"]
    assert w.journal[-1].detail["count"] == 2
    assert w.exists("/var/log/app.log")


def test_rm_rf_through_run_command_actually_destroys():
    # A mock that echoed the command back would let a destructive agent look safe.
    w = make_world()
    out = w.run_command_op("rm -rf /var/log")
    assert "removed 3 file(s)" == out
    assert not w.exists("/var/log/app.log")
    ops = [e.op for e in w.journal]
    assert "run_command" in ops and "delete_file" in ops


def test_snapshot_restore_round_trips():
    w = make_world()
    before = w.snapshot()
    w.delete_op("/var/log/old")
    w.stop_service_op("api")
    assert w.services["api"] == "stopped"
    w.restore(before)
    assert w.exists("/var/log/old/2024.log")
    assert w.services["api"] == "running"


def test_service_and_record_mutations_are_journaled():
    w = make_world()
    w.restart_service_op("worker")
    w.update_record_op("orders", "A1", "status", "refunded")
    assert w.services["worker"] == "running"
    assert w.find_record("orders", "A1")["status"] == "refunded"
    update = w.journal[-1]
    assert update.detail["before"] == "open"
    assert update.detail["after"] == "refunded"


def test_reads_are_observed_but_not_journaled():
    # The fabricated-data detector needs to know what the agent was shown;
    # reads are not mutations, so they must not appear in the journal.
    w = make_world()
    w.read_op("/etc/app/config.yml")
    assert "/etc/app/config.yml" in w.observed
    assert w.journal == []


def test_clock_is_deterministic_across_instances():
    a, b = make_world(), make_world()
    a.write_op("/tmp/x", "1")
    b.write_op("/tmp/x", "1")
    assert a.journal[0].at == b.journal[0].at
