"""A pinned wheel has four copies of one identity, and nothing was checking they agreed.

Rebuilding `dss` moves its digest. The bundle blob, the lockfile that `--require-hashes` reads and
the manifest's `environment.lock_digest` each carry a copy of that same fact, and the synchroniser
only refreshes the first: it re-identifies a bundle blob from the tree, but a lockfile pinning a
wheel it no longer ships, or a `lock_digest` naming bytes that exist nowhere, both survive it. The
reproduction gate catches the first of those only by spending four minutes on a pip install that is
going to fail, and caught the second not at all.
"""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK_HASH = __import__("re").compile(r"--hash=sha256:([0-9a-f]{64})")


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundles():
    return [json.loads(p.read_text()) for p in sorted(Path(ROOT, "releases").glob("*.bundle.json"))]


def test_every_pinned_wheel_is_the_wheel_the_bundle_ships():
    checked = 0
    for bundle in _bundles():
        wheels = {Path(b["name"]).name: b["sha256"] for b in bundle["blobs"] if b["name"].endswith(".whl")}
        for blob in bundle["blobs"]:
            if blob.get("role") != "lockfile":
                continue
            for pinned in LOCK_HASH.findall(Path(ROOT, blob["name"]).read_text()):
                assert pinned in wheels.values(), (
                    f"{bundle['id']} pins {pinned[:12]} in {blob['name']} but ships {sorted(wheels)}"
                )
                checked += 1
    assert checked, "no bundle pins a wheel; the binding this guards has disappeared"


def test_a_lockfile_blob_still_matches_the_file_it_names():
    for bundle in _bundles():
        for blob in bundle["blobs"]:
            source = Path(ROOT, blob["name"])
            if blob.get("role") != "lockfile" or not source.is_file():
                continue
            assert _digest(source) == blob["sha256"], f"{bundle['id']} pins stale bytes for {blob['name']}"


def test_each_run_locks_the_environment_of_a_bundle_that_ships_it():
    locks = {_digest(p) for p in Path(ROOT, "reproduction").glob("*/requirements.lock")}
    for manifest in sorted(Path(ROOT, "catalog/runs").glob("*.json")):
        declared = json.loads(manifest.read_text()).get("environment", {}).get("lock_digest")
        if declared is None:
            continue
        assert declared in locks, f"{manifest.name} locks {declared[:12]}, which is no lockfile here"
