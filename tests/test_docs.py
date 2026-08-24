"""Keep the published documents honest.

A taxonomy document that drifts from the implementation is worse than none: it
is a spec people might adopt, describing behaviour the tool no longer has.
"""

import re
from pathlib import Path

import pytest

from agentcheck.detect.detectors import DETECTORS
from agentcheck.detect.taxonomy import TAXONOMY, deterministic_share
from agentcheck.gen.mutations import MUTATIONS

DOCS = Path(__file__).resolve().parent.parent / "docs"
TAXONOMY_DOC = DOCS / "TAXONOMY.md"
README = DOCS.parent / "README.md"


@pytest.fixture(scope="module")
def spec_text():
    return TAXONOMY_DOC.read_text(encoding="utf-8")


@pytest.mark.parametrize("mode_id", sorted(TAXONOMY))
def test_every_mode_is_documented(mode_id, spec_text):
    assert f"`{mode_id}`" in spec_text, f"{mode_id} is implemented but not in the spec"


@pytest.mark.parametrize("mode_id", sorted(TAXONOMY))
def test_documented_severity_matches_the_code(mode_id, spec_text):
    mode = TAXONOMY[mode_id]
    heading = re.search(rf"### \d+\. `{mode_id}` · (\w+)", spec_text)
    assert heading, f"no heading for {mode_id}"
    assert heading.group(1) == mode.severity, (
        f"{mode_id}: spec says {heading.group(1)}, code says {mode.severity}"
    )


def test_spec_documents_no_modes_that_do_not_exist(spec_text):
    documented = set(re.findall(r"### \d+\. `(\w+)`", spec_text))
    assert documented == set(TAXONOMY), (
        f"spec and code disagree: only in spec {documented - set(TAXONOMY)}, "
        f"only in code {set(TAXONOMY) - documented}"
    )


def test_mode_count_claims_are_accurate(spec_text):
    det, total = deterministic_share()
    assert f"Ten ways an agent fails" in spec_text
    assert total == 10, "the spec's title says ten; update both together"
    assert det == total, "the spec claims no mode needs a model"
    assert len(DETECTORS) == total, "every mode needs exactly one detector"


def test_readme_taxonomy_table_matches_the_code():
    text = README.read_text(encoding="utf-8")
    for mode_id, mode in TAXONOMY.items():
        row = re.search(rf"\| `{mode_id}` \|[^|]*\| (\w+) \|", text)
        assert row, f"{mode_id} missing from the README table"
        assert row.group(1) == mode.severity, (
            f"{mode_id}: README says {row.group(1)}, code says {mode.severity}"
        )


def test_every_mutation_is_listed_in_the_progress_log():
    # The plain-language log is what the teammate reads; a mutation missing from
    # it is a mutation nobody outside the code knows exists.
    text = (DOCS / "PROGRESS.md").read_text(encoding="utf-8")
    for mutation in MUTATIONS:
        readable = mutation.name.replace("_", " ")
        assert readable in text or mutation.name in text, (
            f"{mutation.name} is not explained in PROGRESS.md"
        )


def test_taxonomy_doc_states_its_limits(spec_text):
    # An honest spec says what it cannot do. This is the section a technical
    # reader checks first.
    assert "## Limits" in spec_text
    for claim in ("Sim-to-real", "Semantic quality", "Nondeterministic agents"):
        assert claim in spec_text
