import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest

from decluster.source_snapshot import (
    SourceSnapshotError,
    fetch_source,
    load_source_snapshot,
    verify_normalized_source,
    verify_source,
)


ROOT_KEYS = {
    "schema_version", "id", "title", "canonical_url", "retrieval_url",
    "retrieved_at", "format", "content", "structure", "normalization",
    "license", "redistribution", "availability", "interpretation",
}


def document(payload):
    return {
        "schema_version": 1,
        "id": "source",
        "title": "Source",
        "canonical_url": "https://example.invalid/source",
        "retrieval_url": "https://example.invalid/export",
        "retrieved_at": "2026-09-05T00:00:00Z",
        "format": "application/json",
        "content": {
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "structure": {},
        "normalization": {},
        "license": "unknown",
        "redistribution": "unknown",
        "availability": "remote",
        "interpretation": "fixture",
    }


def notebook_document(payload):
    value = document(payload)
    value["structure"] = {
        "cells": 1,
        "code_cells": 1,
        "markdown_cells": 0,
        "display_data_outputs": 0,
        "execute_result_outputs": 0,
    }
    value["normalization"] = {
        "algorithm": "jq-cS-strip-runtime-v1",
        "tool": "jq 1.8.1",
        "removed": [
            ".cells[].outputs",
            ".cells[].execution_count",
            ".metadata.colab.authorship_tag",
            ".metadata.colab.provenance",
        ],
        "serialization": "jq -cS with one trailing LF; not RFC 8785 JCS",
        "source_only_sha256": "539b2989c3df9ae53831a9d23599aa219ff77def7cb6aae22512580b25dd7ef3",
    }
    return value


def write_manifest(path, value):
    assert set(value) == ROOT_KEYS
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_source_snapshot_verifies_exact_bytes(tmp_path):
    payload = b'{"notebook":true}\n'
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", document(payload))
    )
    source = tmp_path / "source.ipynb"
    source.write_bytes(payload)
    assert verify_source(manifest, source) == manifest


def test_source_snapshot_rejects_modified_bytes(tmp_path):
    payload = b"original"
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", document(payload))
    )
    source = tmp_path / "source.ipynb"
    source.write_bytes(b"modified")
    with pytest.raises(SourceSnapshotError, match="identity mismatch"):
        verify_source(manifest, source)


def test_source_snapshot_fetch_is_identity_checked_and_atomic(tmp_path):
    payload = b"locked notebook"
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", document(payload))
    )
    destination = tmp_path / "source.ipynb"
    opener = lambda _, **__: BytesIO(payload)
    assert fetch_source(manifest, destination, opener=opener) == manifest
    assert destination.read_bytes() == payload

    with pytest.raises(SourceSnapshotError, match="identity mismatch"):
        fetch_source(manifest, destination, opener=lambda _, **__: BytesIO(b"changed"))
    assert destination.read_bytes() == payload


def test_source_snapshot_fetch_rejects_oversized_response(tmp_path):
    payload = b"small"
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", document(payload))
    )
    with pytest.raises(SourceSnapshotError, match="exceeds locked size"):
        fetch_source(
            manifest, tmp_path / "source.ipynb", opener=lambda _, **__: BytesIO(b"too large")
        )


def test_source_snapshot_wraps_transport_failure(tmp_path):
    payload = b"source"
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", document(payload))
    )

    def unavailable(_, **__):
        raise OSError("offline")

    with pytest.raises(SourceSnapshotError, match="download failed"):
        fetch_source(manifest, tmp_path / "source.ipynb", opener=unavailable)


def test_normalization_pipeline_has_a_committed_golden_fixture(tmp_path):
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 0,
        "metadata": {"colab": {"authorship_tag": "remove", "provenance": []}},
        "cells": [{
            "cell_type": "code",
            "metadata": {},
            "source": ["x = 1\n"],
            "execution_count": 1,
            "outputs": [],
        }],
    }
    payload = json.dumps(notebook, separators=(",", ":")).encode()
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", notebook_document(payload))
    )
    source = tmp_path / "source.ipynb"
    source.write_bytes(payload)
    assert verify_normalized_source(manifest, source) == manifest


def test_fetch_validates_normalization_before_replacing_destination(tmp_path):
    payload = json.dumps({"cells": []}, separators=(",", ":")).encode()
    value = notebook_document(payload)
    manifest = load_source_snapshot(write_manifest(tmp_path / "source.json", value))
    destination = tmp_path / "source.ipynb"
    destination.write_bytes(b"preserve")
    with pytest.raises(SourceSnapshotError, match="structure mismatch"):
        fetch_source(manifest, destination, opener=lambda _, **__: BytesIO(payload))
    assert destination.read_bytes() == b"preserve"


def test_radix_lock_records_raw_and_source_only_identities():
    root = Path(__file__).resolve().parents[1]
    path = root / "catalog" / "source-snapshots" / "radix-notebook-v1.json"
    snapshot = load_source_snapshot(path)
    raw = json.loads(path.read_text())
    assert snapshot.sha256 == "afaee22d223b442774eeaa50f3da00c97b1fba5c7c300b5d3cde56ddc57ff48f"
    assert raw["normalization"]["source_only_sha256"] == "a8a9c3d6f70f42c928490ba5974569d6846ff0906cb87481993a3dc6ed2d83f9"
    assert snapshot.redistribution == "unknown"


def test_radix_export_recomputes_normalized_identity_when_available():
    source = Path("/tmp/radix-source")
    if not source.is_file():
        pytest.skip("audited external export not present")
    root = Path(__file__).resolve().parents[1]
    manifest = load_source_snapshot(
        root / "catalog" / "source-snapshots" / "radix-notebook-v1.json"
    )
    assert verify_normalized_source(manifest, source) == manifest


def test_content_size_rejects_boolean(tmp_path):
    value = document(b"x")
    value["content"]["bytes"] = True
    with pytest.raises(SourceSnapshotError, match="content identity is invalid"):
        load_source_snapshot(write_manifest(tmp_path / "source.json", value))


def test_manifest_text_fields_are_strict(tmp_path):
    value = document(b"x")
    value["title"] = {"not": "text"}
    with pytest.raises(SourceSnapshotError, match="title is invalid"):
        load_source_snapshot(write_manifest(tmp_path / "source.json", value))


def test_malformed_notebook_is_a_structured_error(tmp_path):
    payload = b'{"cells":[null]}'
    manifest = load_source_snapshot(
        write_manifest(tmp_path / "source.json", notebook_document(payload))
    )
    source = tmp_path / "source.ipynb"
    source.write_bytes(payload)
    with pytest.raises(SourceSnapshotError, match="cells are missing"):
        verify_normalized_source(manifest, source)
