import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest

from decluster.data_manifest import ManifestError
from decluster.evidence_bundle import (
    BlobStatus,
    AcquisitionStatus,
    BundleBootstrapError,
    MaterializationStatus,
    ReadinessIssueKind,
    ReproductionStatus,
    assess_reproduction_readiness,
    blob_path,
    bootstrap_bundle,
    ingest_blob,
    load_bundle,
    verify_bundle,
)


def index_for(payload):
    return {
        "schema_version": 1,
        "id": "evidence-v1",
        "capabilities": ["verify_outputs"],
        "runs": ["run-v1"],
        "blobs": [{
            "name": "catalog/runs/run-v1.json",
            "role": "run_manifest",
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "locations": {
                "canonical": "https://primary.invalid/run",
                "mirrors": ["https://mirror.invalid/run"],
            },
        }],
        "limitations": ["environment is not bundled"],
    }


def write_index(tmp_path, raw):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(raw))
    return path


def test_ingest_and_verify_are_content_addressed_and_idempotent(tmp_path):
    payload = b'{"run":1}\n'
    source = tmp_path / "run.json"
    source.write_bytes(payload)
    store = tmp_path / "store"
    identity = ingest_blob(source, store)
    assert blob_path(store, identity.sha256).read_bytes() == payload
    assert ingest_blob(source, store) == identity

    bundle = load_bundle(write_index(tmp_path, index_for(payload)))
    assert verify_bundle(bundle, store)[0].status is BlobStatus.VERIFIED


def test_verification_distinguishes_missing_and_corrupt_blobs(tmp_path):
    payload = b"expected"
    bundle = load_bundle(write_index(tmp_path, index_for(payload)))
    store = tmp_path / "store"
    check = verify_bundle(bundle, store)[0]
    assert check.status is BlobStatus.MISSING
    assert check.actual is None

    destination = blob_path(store, hashlib.sha256(payload).hexdigest())
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"tampered")
    assert verify_bundle(bundle, store)[0].status is BlobStatus.IDENTITY_MISMATCH


def test_reproduction_capability_requires_complete_environment_roles(tmp_path):
    raw = index_for(b"manifest")
    raw["capabilities"].append("reproduce_runs")
    with pytest.raises(ManifestError, match="missing roles"):
        load_bundle(write_index(tmp_path, raw))


def test_reproduction_capability_allows_a_dependency_free_environment(tmp_path):
    raw = index_for(b"manifest")
    raw["capabilities"].append("reproduce_runs")
    for role, name, payload in (
        ("source", "sources/source.tar", b"source"),
        ("lockfile", "reproduction/run/requirements.lock", b"# No third-party dependencies.\n"),
        ("environment", "reproduction/run/environment.json", b"environment"),
    ):
        raw["blobs"].append({
            "name": name,
            "role": role,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "locations": {
                "canonical": "https://primary.invalid/blob",
                "mirrors": ["https://mirror.invalid/blob"],
            },
        })

    bundle = load_bundle(write_index(tmp_path, raw))

    assert all(blob.role.value != "dependency" for blob in bundle.blobs)


@pytest.mark.parametrize("mutation", [
    lambda raw: raw["blobs"].append(dict(raw["blobs"][0])),
    lambda raw: raw["capabilities"].append("verify_outputs"),
    lambda raw: raw["blobs"][0].update(sha256="ABC"),
])
def test_bundle_rejects_ambiguous_or_invalid_identity(tmp_path, mutation):
    raw = index_for(b"manifest")
    mutation(raw)
    with pytest.raises(ManifestError):
        load_bundle(write_index(tmp_path, raw))


def test_bootstrap_falls_back_verifies_and_materializes_without_future_network(tmp_path):
    payload = b"manifest"
    bundle = load_bundle(write_index(tmp_path, index_for(payload)))
    calls = []

    def opener(url):
        calls.append(url)
        return BytesIO(b"wrong" if "primary" in url else payload)

    result = bootstrap_bundle(bundle, tmp_path / "store", tmp_path / "checkout", opener=opener)
    assert result[0].acquisition is AcquisitionStatus.DOWNLOADED
    assert result[0].materialization is MaterializationStatus.MATERIALIZED
    assert result[0].path.read_bytes() == payload
    assert calls == ["https://primary.invalid/run", "https://mirror.invalid/run"]

    cached = bootstrap_bundle(
        bundle, tmp_path / "store", tmp_path / "checkout",
        opener=lambda _: pytest.fail("network used"),
    )
    assert cached[0].acquisition is AcquisitionStatus.ALREADY_AVAILABLE
    assert cached[0].materialization is MaterializationStatus.ALREADY_MATERIALIZED


def test_bootstrap_preserves_divergent_destination(tmp_path):
    payload = b"manifest"
    bundle = load_bundle(write_index(tmp_path, index_for(payload)))
    target = tmp_path / "checkout" / "catalog" / "runs" / "run-v1.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"local work")
    with pytest.raises(BundleBootstrapError, match="destination_identity_mismatch"):
        bootstrap_bundle(
            bundle, tmp_path / "store", tmp_path / "checkout",
            opener=lambda _: BytesIO(payload),
        )
    assert target.read_bytes() == b"local work"


@pytest.mark.parametrize(
    "index", sorted((Path(__file__).resolve().parents[1] / "releases").glob("*.bundle.json"))
)
def test_committed_bundle_reports_only_public_distribution_blockers(index):
    root = Path(__file__).resolve().parents[1]
    bundle = load_bundle(index)
    readiness = assess_reproduction_readiness(bundle, root / "artifacts", root)
    assert readiness.status is ReproductionStatus.BLOCKED
    kinds = {issue.kind for issue in readiness.issues}
    assert kinds == {
        ReadinessIssueKind.CANONICAL_LOCATION_MISSING,
        ReadinessIssueKind.MIRROR_MISSING,
    }
