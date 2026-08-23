"""Report writers and the CLI surface."""

import json
import xml.etree.ElementTree as ET

import pytest

from agentcheck.cli import main
from agentcheck.engine import run_suite
from agentcheck.gen.builtin import builtin_seeds
from agentcheck.gen.mutations import expand
from agentcheck.report import to_html, to_json, to_junit
from agentcheck.toolkits.devops import devops_toolset
from demo_agents import HardenedDevOpsAgent, NaiveDevOpsAgent

TOOLS = devops_toolset()


@pytest.fixture(scope="module")
def suite():
    return expand(builtin_seeds(), pairs=False)


@pytest.fixture(scope="module")
def failing(suite):
    return run_suite(suite, NaiveDevOpsAgent, TOOLS)


@pytest.fixture(scope="module")
def clean(suite):
    return run_suite(suite, HardenedDevOpsAgent, TOOLS)


# -- JUnit ------------------------------------------------------------------


def test_junit_is_well_formed_xml(failing):
    root = ET.fromstring(to_junit(failing))
    testsuite = root.find("testsuite")
    assert int(testsuite.get("tests")) == failing.total
    assert int(testsuite.get("failures")) == failing.total - failing.passed


def test_junit_groups_scenarios_by_seed(failing):
    root = ET.fromstring(to_junit(failing))
    classnames = {tc.get("classname") for tc in root.iter("testcase")}
    assert "log-cleanup" in classnames
    assert "devops" not in classnames, "base scenarios should group under their seed"


def test_junit_failure_carries_the_mode_and_evidence(failing):
    root = ET.fromstring(to_junit(failing))
    failures = [f for f in root.iter("failure")]
    assert failures
    assert failures[0].get("type")
    assert "task:" in failures[0].text
    assert "fingerprint:" in failures[0].text


def test_junit_escapes_hostile_content(suite):
    """Agent output ends up inside XML, so it must not be able to break it."""

    class Rude:
        id = "rude"

        def begin(self, task, tools):
            pass

        def step(self, obs):
            from agentcheck.runtime.agent import FinishAction

            return FinishAction('</failure></testcase><injected attr="x">& < >')

    card = run_suite(suite[:2], Rude, TOOLS)
    root = ET.fromstring(to_junit(card))  # raises if the injection escaped
    assert root.find("testsuite") is not None


def test_clean_run_has_no_failure_elements(clean):
    root = ET.fromstring(to_junit(clean))
    assert list(root.iter("failure")) == []


# -- JSON -------------------------------------------------------------------


def test_json_round_trips_and_carries_the_taxonomy(failing):
    payload = json.loads(to_json(failing))
    assert payload["total"] == failing.total
    assert payload["findings_deterministic"] == payload["findings_total"]
    assert "destructive_action" in payload["taxonomy"]
    assert payload["results"][0]["trace"]["calls"] is not None


def test_json_accepts_extra_metadata(failing):
    payload = json.loads(to_json(failing, suite_hash="abc123"))
    assert payload["suite_hash"] == "abc123"


# -- HTML -------------------------------------------------------------------


def test_html_is_self_contained(failing):
    out = to_html(failing)
    assert out.startswith("<!doctype html>")
    # No external fetches: the report has to open on a broken conference wifi.
    for marker in ("http://", "https://", "<script"):
        assert marker not in out, f"report should not reference {marker}"


def test_html_escapes_agent_output(suite):
    class Rude:
        id = "rude"

        def begin(self, task, tools):
            pass

        def step(self, obs):
            from agentcheck.runtime.agent import FinishAction

            return FinishAction("<script>alert(1)</script>")

    out = to_html(run_suite(suite[:2], Rude, TOOLS))
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_html_states_the_deterministic_share(failing):
    # Normalise whitespace: the template wraps this sentence across lines, and
    # the claim matters, not where it happens to break.
    out = " ".join(to_html(failing).split())
    det, total = failing.deterministic_finding_share()
    assert "decided by a property check against recorded world state" in out
    assert f"{det} of {total} findings" in out


def test_html_handles_a_clean_run(clean):
    out = to_html(clean)
    assert "Nothing failed." in out or "No findings" in out


# -- CLI --------------------------------------------------------------------


def test_cli_scenarios_count(capsys):
    assert main(["scenarios", "--count"]) == 0
    assert int(capsys.readouterr().out.strip()) > 150


def test_cli_taxonomy_lists_every_mode(capsys):
    assert main(["taxonomy"]) == 0
    out = capsys.readouterr().out
    for mode in ("destructive_action", "hallucinated_success", "goal_drift"):
        assert mode in out


def test_cli_mutations_lists_the_ladder(capsys):
    assert main(["mutations"]) == 0
    out = capsys.readouterr().out
    assert "time_pressure" in out and "distractor_entity" in out


def test_cli_run_writes_every_report_format(tmp_path, capsys):
    html, js, xml = (tmp_path / "r.html", tmp_path / "r.json", tmp_path / "r.xml")
    code = main(
        [
            "run", "--agent", "demo_agents:HardenedDevOpsAgent",
            "--no-pairs", "--out", str(html), "--json", str(js), "--junit", str(xml),
        ]
    )
    capsys.readouterr()
    assert code == 0
    assert html.read_text().startswith("<!doctype html>")
    assert json.loads(js.read_text())["pass_rate"] == 1.0
    ET.fromstring(xml.read_text())


def test_cli_fail_on_findings_exits_nonzero(tmp_path, capsys):
    code = main(["run", "--agent", "demo_agents:NaiveDevOpsAgent", "--no-pairs",
                 "--fail-on-findings"])
    capsys.readouterr()
    assert code == 1


def test_cli_regression_gate(tmp_path, capsys):
    history = tmp_path / "h.jsonl"
    common = ["run", "--no-pairs", "--label", "app", "--history", str(history),
              "--fail-on-new"]

    # First run has no baseline: it establishes one and must not fail the build.
    assert main([*common, "--agent", "demo_agents:HardenedDevOpsAgent"]) == 0
    capsys.readouterr()

    # Shipping the naive agent is a regression and must break CI.
    assert main([*common, "--agent", "demo_agents:NaiveDevOpsAgent"]) == 1
    assert "new failure" in capsys.readouterr().out

    # Reverting to the good agent clears the gate again.
    assert main([*common, "--agent", "demo_agents:HardenedDevOpsAgent"]) == 0
    capsys.readouterr()


def test_cli_rejects_a_bad_agent_spec():
    with pytest.raises(SystemExit):
        main(["run", "--agent", "not_a_module_at_all:Thing", "--no-pairs"])
    with pytest.raises(SystemExit):
        main(["run", "--agent", "missing-colon", "--no-pairs"])
