import hashlib
import json

import pytest

from decluster.data_manifest import ManifestError
from decluster.evidence_bundle import (
    BlobStatus,
    blob_path,
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
