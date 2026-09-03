import platform
from pathlib import Path
import sys

import pytest

from decluster.evidence_bundle import (
    BlobStatus,
    bootstrap_bundle,
    load_bundle,
    reproduce_bundle,
    verify_bundle,
)
from decluster.result_artifacts import content_identity


ROOT = Path(__file__).resolve().parents[1]


def test_every_committed_bundle_is_complete_and_content_verified():
    indexes = sorted((ROOT / "releases").glob("*.bundle.json"))
    assert indexes, "no evidence bundle is committed"
    referenced = set()
    for index in indexes:
        bundle = load_bundle(index)
        checks = verify_bundle(bundle, ROOT / "artifacts")
        failures = [check for check in checks if check.status is not BlobStatus.VERIFIED]
        assert not failures, f"{index}: {failures}"
        for blob in bundle.blobs:
            referenced.add(blob.content.sha256)
            named = ROOT / blob.name
            if named.is_file():
                assert content_identity(named) == blob.content, (
                    f"{index}: {blob.name} drifted from its bundled identity"
                )
    stored = {
        path.parent.name + path.name
        for path in (ROOT / "artifacts" / "sha256").glob("*/*")
        if path.is_file()
    }
    assert stored == referenced, (
        f"artifact store has missing={sorted(referenced - stored)} "
        f"or orphaned={sorted(stored - referenced)} blobs"
    )


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 13) or platform.system() != "Darwin"
    or platform.machine() != "arm64",
    reason="the first reproduction environment targets CPython 3.13 on macOS arm64",
)
def test_committed_bundle_reproduces_from_materialized_contents(tmp_path):
    bundle = load_bundle(ROOT / "releases" / "exact-oracle-evidence-v1.bundle.json")
    materialized = tmp_path / "bundle"
    bootstrap_bundle(bundle, ROOT / "artifacts", materialized)
    outputs = reproduce_bundle(bundle, materialized, tmp_path / "work")
    assert {path.name for path in outputs} == {
        "exact-oracle-audit-v1.json", "exact-oracle-audit-v1.md",
    }
