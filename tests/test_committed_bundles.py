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
from decluster.data_catalog import load_dataset_catalog
from decluster.data_manifest import load_run_manifest
from decluster.reference_registry import load_claims, load_sources
from decluster.result_artifacts import content_identity


ROOT = Path(__file__).resolve().parents[1]


def expected_output_names(bundle):
    sources = load_sources(ROOT / "catalog" / "ctp-sources.json")
    claims = load_claims(
        ROOT / "catalog" / "ctp-claims.json", {source.id for source in sources}
    )
    datasets = {dataset.id: dataset for dataset in load_dataset_catalog(ROOT)}
    names = set()
    for run_id in bundle.runs:
        manifest = load_run_manifest(
            ROOT / "catalog" / "runs" / f"{run_id}.json",
            claim_ids={claim.id for claim in claims},
            datasets=datasets,
        )
        names.update(Path(output.path).name for output in manifest.outputs)
    return names


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
@pytest.mark.parametrize("index", sorted((ROOT / "releases").glob("*.bundle.json")))
@pytest.mark.reproduction
def test_committed_bundle_reproduces_from_materialized_contents(tmp_path, index):
    bundle = load_bundle(index)
    materialized = tmp_path / "bundle"
    bootstrap_bundle(bundle, ROOT / "artifacts", materialized)
    outputs = reproduce_bundle(bundle, materialized, tmp_path / "work")
    assert {path.name for path in outputs} == expected_output_names(bundle)
