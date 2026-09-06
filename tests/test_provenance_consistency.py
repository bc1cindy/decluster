"""What a run manifest says about its code has to match what its bundle actually executes.

`reproduce` extracts the bundle's source archive and runs *that* code, so the archive is the
runtime, not the working tree. A manifest naming a different revision is not caught by anything
else here: the outputs still verify, the reproduction still passes, and the declaration is still
wrong. That combination is how three manifests went a whole correction round claiming a clean tree
at a revision their own experiment module predates.

Every check needs git history. A shallow checkout skips rather than passes, and says what went
unchecked.
"""
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = sorted((ROOT / "releases").glob("*.bundle.json"))


def _git(*args):
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True)


def _has_history():
    return not (ROOT / ".git" / "shallow").exists() and _git("rev-parse", "HEAD").returncode == 0


requires_history = pytest.mark.skipif(
    not _has_history(), reason="shallow or absent git history; revision consistency went unchecked"
)


def _bundle_runs():
    for index in BUNDLES:
        bundle = json.loads(index.read_text())
        archive = next((b["name"] for b in bundle["blobs"] if b["role"] == "source"), None)
        for run in bundle["runs"]:
            yield index.name, run, archive


def _manifest(run):
    return json.loads((ROOT / "catalog" / "runs" / f"{run}.json").read_text())


def _module_path(manifest):
    module = next((a for a in manifest["command"]["argv"] if a.startswith("decluster.")), None)
    if module is None:
        return None
    return "decluster/" + module.split("decluster.", 1)[1].replace(".", "/") + ".py"


def _archive_revision(archive):
    # runtime_snapshot names the archive decluster-<short revision>-runtime.tar
    return archive.split("-")[1]


def test_bundles_exist_to_check():
    assert BUNDLES, "no evidence bundle is committed"


@requires_history
def test_every_declared_revision_is_a_real_commit():
    for path in sorted((ROOT / "catalog" / "runs").glob("*.json")):
        revision = json.loads(path.read_text())["code"]["revision"]
        assert _git("cat-file", "-e", f"{revision}^{{commit}}").returncode == 0, (
            f"{path.name} declares revision {revision}, which is not a commit here"
        )


@requires_history
def test_no_run_predates_the_archive_its_bundle_ships():
    for index, run, archive in _bundle_runs():
        assert archive, f"{index} ships no source archive"
        revision = _manifest(run)["code"]["revision"]
        assert _git("merge-base", "--is-ancestor", revision,
                    _archive_revision(archive)).returncode == 0, (
            f"{index}: {run} declares {revision[:7]}, which is not an ancestor of the "
            f"archive's {_archive_revision(archive)}"
        )


@requires_history
def test_the_experiment_a_bundle_runs_is_the_one_its_manifest_names():
    """The declared revision and the archive's revision must hold the same experiment module.

    When they differ the bundle reproduces with code the manifest does not describe. The outputs
    can still match — they did — so nothing else in the suite notices.
    """
    drifted = []
    for index, run, archive in _bundle_runs():
        manifest = _manifest(run)
        path = _module_path(manifest)
        if path is None:
            continue
        declared = _git("show", f"{manifest['code']['revision']}:{path}")
        shipped = _git("show", f"{_archive_revision(archive)}:{path}")
        if declared.returncode or shipped.returncode or declared.stdout != shipped.stdout:
            drifted.append(f"{run} ({manifest['code']['revision'][:7]} vs "
                           f"{_archive_revision(archive)}): {path}")
    assert not drifted, "manifest revision and shipped archive disagree on:\n  " + "\n  ".join(drifted)


def test_a_declared_dependency_revision_matches_what_its_artifact_recorded():
    """A run that pins a dependency revision and an output that records one must agree."""
    for path in sorted((ROOT / "catalog" / "runs").glob("*.json")):
        manifest = json.loads(path.read_text())
        declared = {d["revision"] for d in manifest["environment"].get("dependencies", ())
                    if d.get("revision")}
        if not declared:
            continue
        for output in manifest["outputs"]:
            target = ROOT / output["path"]
            if target.suffix != ".json" or not target.is_file():
                continue
            recorded = _recorded_revisions(json.loads(target.read_text()))
            unmatched = recorded - declared
            assert not unmatched, (
                f"{path.name} declares {sorted(declared)} but {output['path']} records "
                f"{sorted(unmatched)}"
            )


def _recorded_revisions(value):
    """Every value under a key ending in `_rev`/`revision` anywhere in the artifact."""
    found = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and (key.endswith("_rev") or key.endswith("revision")):
                found.add(item)
            else:
                found |= _recorded_revisions(item)
    elif isinstance(value, list):
        for item in value:
            found |= _recorded_revisions(item)
    return found
