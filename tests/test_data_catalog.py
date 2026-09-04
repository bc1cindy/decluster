import json
from io import BytesIO
from pathlib import Path

import pytest

from decluster.data_catalog import (
    DatasetStatus,
    DatasetFetchError,
    FetchAttemptStatus,
    FetchStatus,
    DatasetPrepareError,
    PrepareFailure,
    PrepareStatus,
    catalog_status,
    dataset_path,
    dataset_status,
    load_dataset_catalog,
    require_verified_datasets,
    fetch_dataset,
    prepare_dataset,
)
from decluster.evidence_bundle import blob_path
from decluster.data_manifest import ManifestError, load_dataset_manifest


ROOT = Path(__file__).resolve().parents[1]


def manifest_document(dataset_id, local_path, payload):
    import hashlib
    return {
        "schema_version": 1,
        "id": dataset_id,
        "title": dataset_id,
        "kind": "git_fixture",
        "schema": "bytes-v1",
        "format": "bin",
        "content": {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()},
        "locations": {"local_path": local_path, "canonical": None, "mirrors": []},
        "source": {"provider": "test", "snapshot_time": None, "recipe": None, "recipe_sha256": None},
        "license": {"data": "MIT", "recipe": None},
        "redistribution": "allowed",
        "sensitivity": "synthetic",
        "normalization": {"code_revision": None, "parameters": {}, "parents": []},
        "determinism": {"ordering": "stored bytes", "rng_algorithm": None, "rng_seed": None},
    }


def write_manifest(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document))
    return load_dataset_manifest(path)


def test_dataset_status_has_distinct_verified_missing_and_mismatch_states(tmp_path):
    payload = b"dataset"
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("sample", "data/sample.bin", payload)
    )
    assert dataset_status(manifest, tmp_path).status is DatasetStatus.MISSING
    target = tmp_path / "data" / "sample.bin"
    target.parent.mkdir()
    target.write_bytes(b"wrong")
    assert dataset_status(manifest, tmp_path).status is DatasetStatus.IDENTITY_MISMATCH
    target.write_bytes(payload)
    assert dataset_status(manifest, tmp_path).status is DatasetStatus.VERIFIED


def test_dataset_paths_cannot_escape_the_project_root(tmp_path):
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("escape", "../outside.bin", b"x")
    )
    with pytest.raises(ManifestError, match="escapes project root"):
        dataset_path(manifest, tmp_path)


def test_catalog_is_sorted_and_duplicate_ids_are_rejected(tmp_path):
    catalog = tmp_path / "catalog" / "datasets"
    write_manifest(catalog / "b.json", manifest_document("b", "b.bin", b"b"))
    write_manifest(catalog / "a.json", manifest_document("a", "a.bin", b"a"))
    assert [dataset.id for dataset in load_dataset_catalog(tmp_path)] == ["a", "b"]
    write_manifest(catalog / "duplicate.json", manifest_document("a", "c.bin", b"c"))
    with pytest.raises(ManifestError, match="duplicate dataset id"):
        load_dataset_catalog(tmp_path)


def test_empty_catalog_is_not_vacuously_verified(tmp_path):
    with pytest.raises(ManifestError, match="catalog is empty"):
        require_verified_datasets(tmp_path)


def test_require_verified_refuses_partial_catalog(tmp_path):
    catalog = tmp_path / "catalog" / "datasets"
    write_manifest(catalog / "a.json", manifest_document("a", "a.bin", b"a"))
    with pytest.raises(ManifestError, match="a=missing"):
        require_verified_datasets(tmp_path)


def test_committed_catalog_is_fully_verified():
    checks = catalog_status(ROOT)
    assert len(checks) == 13
    assert all(check.status is DatasetStatus.VERIFIED for check in checks)
    assert len(require_verified_datasets(ROOT)) == 13


def test_fetch_uses_mirror_after_identity_mismatch_and_is_then_cached(tmp_path):
    payload = b"dataset"
    document = manifest_document("sample", "data/sample.bin", payload)
    document["locations"] = {
        "local_path": "data/sample.bin",
        "canonical": "https://primary.invalid/sample",
        "mirrors": ["https://mirror.invalid/sample"],
    }
    manifest = write_manifest(tmp_path / "manifest.json", document)
    opened = []

    def opener(url):
        opened.append(url)
        return BytesIO(b"wrong" if "primary" in url else payload)

    result = fetch_dataset(manifest, tmp_path / "store", opener=opener)
    assert result.status is FetchStatus.DOWNLOADED
    assert result.source_url == "https://mirror.invalid/sample"
    assert result.path.read_bytes() == payload
    assert opened == ["https://primary.invalid/sample", "https://mirror.invalid/sample"]

    cached = fetch_dataset(
        manifest, tmp_path / "store", opener=lambda _: pytest.fail("network used")
    )
    assert cached.status is FetchStatus.ALREADY_AVAILABLE
    assert cached.source_url is None


def test_fetch_failure_is_structured_and_leaves_no_blob(tmp_path):
    payload = b"expected"
    document = manifest_document("sample", "data/sample.bin", payload)
    document["locations"] = {
        "local_path": "data/sample.bin",
        "canonical": "https://primary.invalid/sample",
        "mirrors": ["https://mirror.invalid/sample"],
    }
    manifest = write_manifest(tmp_path / "manifest.json", document)

    def opener(url):
        if "primary" in url:
            raise OSError("offline")
        return BytesIO(b"tampered")

    with pytest.raises(DatasetFetchError) as raised:
        fetch_dataset(manifest, tmp_path / "store", opener=opener)
    assert [attempt.status for attempt in raised.value.attempts] == [
        FetchAttemptStatus.TRANSPORT_ERROR,
        FetchAttemptStatus.IDENTITY_MISMATCH,
    ]
    assert not list((tmp_path / "store").rglob("*.*"))


def test_fetch_rejects_oversized_response_without_reading_it_unbounded(tmp_path):
    payload = b"small"
    document = manifest_document("sample", "data/sample.bin", payload)
    document["locations"]["canonical"] = "https://primary.invalid/sample"
    manifest = write_manifest(tmp_path / "manifest.json", document)
    with pytest.raises(DatasetFetchError) as raised:
        fetch_dataset(manifest, tmp_path / "store", opener=lambda _: BytesIO(b"x" * 100))
    assert raised.value.attempts[0].status is FetchAttemptStatus.IDENTITY_MISMATCH


def test_prepare_materializes_verified_blob_and_is_idempotent(tmp_path):
    payload = b"dataset"
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("sample", "data/sample.bin", payload)
    )
    store = tmp_path / "store"
    source = blob_path(store, manifest.content.sha256)
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)

    result = prepare_dataset(manifest, tmp_path, store)
    assert result.status is PrepareStatus.MATERIALIZED
    assert result.path.read_bytes() == payload
    assert prepare_dataset(manifest, tmp_path, store).status is PrepareStatus.ALREADY_PREPARED


def test_prepare_requires_verified_store_blob(tmp_path):
    payload = b"dataset"
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("sample", "data/sample.bin", payload)
    )
    store = tmp_path / "store"
    with pytest.raises(DatasetPrepareError) as missing:
        prepare_dataset(manifest, tmp_path, store)
    assert missing.value.failure is PrepareFailure.STORE_MISSING

    source = blob_path(store, manifest.content.sha256)
    source.parent.mkdir(parents=True)
    source.write_bytes(b"tampered")
    with pytest.raises(DatasetPrepareError) as mismatch:
        prepare_dataset(manifest, tmp_path, store)
    assert mismatch.value.failure is PrepareFailure.STORE_IDENTITY_MISMATCH


def test_prepare_reuses_verified_destination_without_requiring_store_copy(tmp_path):
    payload = b"dataset"
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("sample", "data/sample.bin", payload)
    )
    destination = tmp_path / "data" / "sample.bin"
    destination.parent.mkdir()
    destination.write_bytes(payload)
    result = prepare_dataset(manifest, tmp_path, tmp_path / "absent-store")
    assert result.status is PrepareStatus.ALREADY_PREPARED
    assert result.path == destination


def test_prepare_refuses_to_replace_divergent_destination_by_default(tmp_path):
    payload = b"dataset"
    manifest = write_manifest(
        tmp_path / "manifest.json", manifest_document("sample", "data/sample.bin", payload)
    )
    store = tmp_path / "store"
    source = blob_path(store, manifest.content.sha256)
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)
    destination = tmp_path / "data" / "sample.bin"
    destination.parent.mkdir()
    destination.write_bytes(b"local work")

    with pytest.raises(DatasetPrepareError) as mismatch:
        prepare_dataset(manifest, tmp_path, store)
    assert mismatch.value.failure is PrepareFailure.DESTINATION_IDENTITY_MISMATCH
    assert destination.read_bytes() == b"local work"
    assert prepare_dataset(manifest, tmp_path, store, replace=True).status is PrepareStatus.MATERIALIZED
    assert destination.read_bytes() == payload
