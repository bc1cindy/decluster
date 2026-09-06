"""The synchroniser has to move index, store and tree together, or it is worse than doing it by hand.

Each case here is a way the manual procedure went wrong during the audit: a digest updated without
its byte count, a store-only blob treated as missing, an orphan removed before the indexes were
rewritten.
"""
import hashlib
import json
from pathlib import Path

import pytest

from decluster.bundle_sync import Change, synchronise, unresolved

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def store_blob(root, data):
    d = digest(data)
    target = root / "artifacts" / "sha256" / d[:2] / d[2:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return d


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "releases").mkdir()
    (tmp_path / "results").mkdir()
    (tmp_path / "artifacts" / "sha256").mkdir(parents=True)
    return tmp_path


def write_bundle(root, name, blobs):
    index = root / "releases" / f"{name}.bundle.json"
    index.write_text(json.dumps(
        {"schema_version": 1, "id": name, "runs": [], "blobs": blobs}, indent=2) + "\n")
    return index


def blob_for(root, relative):
    data = (root / relative).read_bytes()
    return {"name": relative, "role": "result", "bytes": len(data), "sha256": digest(data)}


def test_a_tree_in_step_needs_no_change(repo):
    (repo / "results" / "a.json").write_text("{}")
    store_blob(repo, b"{}")
    write_bundle(repo, "b1", [blob_for(repo, "results/a.json")])
    assert synchronise(repo, write=False) == ()


def test_an_edited_file_moves_its_byte_count_as_well_as_its_digest(repo):
    target = repo / "results" / "a.json"
    target.write_text("{}")
    write_bundle(repo, "b1", [blob_for(repo, "results/a.json")])
    store_blob(repo, b"{}")
    target.write_text('{"longer": true}')

    changes = synchronise(repo)
    assert Change("identity", "results/a.json", changes[0].detail) in changes
    pinned = json.loads((repo / "releases" / "b1.bundle.json").read_text())["blobs"][0]
    assert (pinned["bytes"], pinned["sha256"]) == (16, digest(b'{"longer": true}'))


def test_the_new_content_lands_in_the_store_and_the_old_leaves_it(repo):
    target = repo / "results" / "a.json"
    target.write_text("{}")
    write_bundle(repo, "b1", [blob_for(repo, "results/a.json")])
    old = store_blob(repo, b"{}")
    target.write_text('{"longer": true}')

    synchronise(repo)
    store = {p.parent.name + p.name for p in (repo / "artifacts" / "sha256").glob("*/*")}
    assert store == {digest(b'{"longer": true}')}
    assert old not in store


def test_a_blob_that_was_never_a_tracked_file_keeps_its_identity(repo):
    wheel = b"not-in-the-tree"
    stored = store_blob(repo, wheel)
    write_bundle(repo, "b1", [{"name": "dependencies/x.whl", "role": "dependency",
                               "bytes": len(wheel), "sha256": stored}])
    assert synchronise(repo, write=False) == ()


def test_a_referenced_blob_with_neither_store_nor_tree_is_reported_not_invented(repo):
    write_bundle(repo, "b1", [{"name": "dependencies/x.whl", "role": "dependency",
                               "bytes": 3, "sha256": digest(b"gone")}])
    changes = synchronise(repo, write=False)
    assert [c.kind for c in changes] == ["unavailable"]
    assert unresolved(changes) == changes


def test_orphans_are_judged_after_every_index_is_rewritten(repo):
    shared = repo / "results" / "shared.json"
    shared.write_text("{}")
    write_bundle(repo, "b1", [blob_for(repo, "results/shared.json")])
    write_bundle(repo, "b2", [blob_for(repo, "results/shared.json")])
    store_blob(repo, b"{}")
    shared.write_text('{"x": 1}')

    synchronise(repo)
    store = {p.parent.name + p.name for p in (repo / "artifacts" / "sha256").glob("*/*")}
    assert store == {digest(b'{"x": 1}')}
    for name in ("b1", "b2"):
        pinned = json.loads((repo / "releases" / f"{name}.bundle.json").read_text())["blobs"][0]
        assert pinned["sha256"] == digest(b'{"x": 1}')


def test_check_mode_reports_without_touching_anything(repo):
    target = repo / "results" / "a.json"
    target.write_text("{}")
    write_bundle(repo, "b1", [blob_for(repo, "results/a.json")])
    store_blob(repo, b"{}")
    target.write_text('{"longer": true}')
    before = (repo / "releases" / "b1.bundle.json").read_text()

    assert synchronise(repo, write=False)
    assert (repo / "releases" / "b1.bundle.json").read_text() == before
    assert {p.parent.name + p.name for p in (repo / "artifacts" / "sha256").glob("*/*")} == {
        digest(b"{}")
    }


def test_the_committed_tree_is_already_in_step():
    drift = synchronise(ROOT, write=False)
    assert not drift, (
        "releases/, artifacts/sha256/ and the tree disagree:\n  "
        + "\n  ".join(f"{c.kind}\t{c.name}\t{c.detail}" for c in drift)
        + "\nRun `decluster-bundle --root . sync` and commit the result."
    )
