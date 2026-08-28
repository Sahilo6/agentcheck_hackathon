"""The dashboard lockfile must be installable by `npm ci`.

This exists because a real deploy failed on it. npm 11 wrote two optional
platform binaries into the lockfile with no `version` field; npm 10 on CI tried
to parse the empty string and died with "Invalid Version:". The site build never
ran, and nothing else in the test suite would have noticed.
"""

import json
from pathlib import Path

import pytest

LOCKFILE = Path(__file__).resolve().parent.parent / "web" / "package-lock.json"


@pytest.fixture(scope="module")
def lockfile():
    if not LOCKFILE.exists():
        pytest.skip("dashboard lockfile not present")
    return json.loads(LOCKFILE.read_text())


def test_every_entry_has_a_version(lockfile):
    missing = [name for name, entry in lockfile["packages"].items() if "version" not in entry]
    assert not missing, (
        "these entries have no version, which makes `npm ci` fail with "
        f"'Invalid Version'. Regenerate the lockfile: {missing[:5]}"
    )


def test_no_entry_has_an_empty_version(lockfile):
    empty = [
        name for name, entry in lockfile["packages"].items() if entry.get("version") == ""
    ]
    assert not empty, empty[:5]


def test_lockfile_matches_the_manifest(lockfile):
    manifest = json.loads((LOCKFILE.parent / "package.json").read_text())
    assert lockfile["name"] == manifest["name"]
    assert lockfile["version"] == manifest["version"]
    # `npm ci` refuses to run at all if these disagree.
    declared = {**manifest.get("dependencies", {}), **manifest.get("devDependencies", {})}
    root = lockfile["packages"][""]
    locked = {**root.get("dependencies", {}), **root.get("devDependencies", {})}
    assert declared == locked, "package.json and the lockfile disagree; run npm install"
