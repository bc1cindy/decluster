"""Moving the runtime archive has to move every record that names it, in one step.

Done by hand it is four edits in a required order — environments, run manifests, bundle source
blobs, then deleting the superseded archive — and skipping any one of them leaves a record
describing a runtime the repository does not ship. That happened three times during the audit
before this existed.
"""
import json

import pytest

from decluster.runtime_snapshot import repoint


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "sources").mkdir()
    old = tmp_path / "sources" / "decluster-aaaaaaa-runtime.tar"
    new = tmp_path / "sources" / "decluster-bbbbbbb-runtime.tar"
    old.write_bytes(b"old")
    new.write_bytes(b"new")

    environment = tmp_path / "reproduction" / "one" / "environment.json"
    environment.parent.mkdir(parents=True)
    environment.write_text(json.dumps(
        {"schema_version": 1, "source_archive": "sources/decluster-aaaaaaa-runtime.tar"}, indent=2) + "\n")

    manifest = tmp_path / "catalog" / "runs" / "one.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"id": "one", "code": {"revision": "a" * 40, "dirty": False}},
                                   indent=2) + "\n")

    index = tmp_path / "releases" / "one.bundle.json"
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps({"id": "one", "blobs": [
        {"name": "sources/decluster-aaaaaaa-runtime.tar", "role": "source"},
        {"name": "results/artifacts/one.json", "role": "result"},
    ]}, indent=2) + "\n")
    return tmp_path, new


def test_every_record_follows_the_new_archive(tree):
    root, archive = tree
    moved, superseded = repoint(root, archive, "b" * 40)
    assert len(moved) == 3 and superseded == ["decluster-aaaaaaa-runtime.tar"]

    environment = json.loads((root / "reproduction" / "one" / "environment.json").read_text())
    assert environment["source_archive"] == "sources/decluster-bbbbbbb-runtime.tar"
    manifest = json.loads((root / "catalog" / "runs" / "one.json").read_text())
    assert manifest["code"]["revision"] == "b" * 40
    blobs = json.loads((root / "releases" / "one.bundle.json").read_text())["blobs"]
    assert blobs[0]["name"] == "sources/decluster-bbbbbbb-runtime.tar"
    assert blobs[1]["name"] == "results/artifacts/one.json"


def test_the_superseded_archive_is_removed_and_the_new_one_kept(tree):
    root, archive = tree
    repoint(root, archive, "b" * 40)
    remaining = sorted(p.name for p in (root / "sources").glob("*.tar"))
    assert remaining == ["decluster-bbbbbbb-runtime.tar"]


def test_repointing_a_tree_already_in_step_changes_nothing(tree):
    root, archive = tree
    repoint(root, archive, "b" * 40)
    moved, superseded = repoint(root, archive, "b" * 40)
    assert moved == [] and superseded == []
