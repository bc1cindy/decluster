"""Strict identities for external research sources that cannot be redistributed."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import urlopen


class SourceSnapshotError(ValueError):
    """An external source lock is malformed or does not match supplied bytes."""


@dataclass(frozen=True)
class SourceSnapshot:
    id: str
    size_bytes: int
    sha256: str
    canonical_url: str
    retrieval_url: str
    redistribution: str
    structure: dict | None
    source_only_sha256: str | None


def load_source_snapshot(path):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceSnapshotError(f"cannot read source snapshot {path}: {exc}") from exc
    required = {
        "schema_version", "id", "title", "canonical_url", "retrieval_url",
        "retrieved_at", "format", "content", "structure", "normalization",
        "license", "redistribution", "availability", "interpretation",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise SourceSnapshotError("source snapshot has missing or unknown fields")
    if document["schema_version"] != 1:
        raise SourceSnapshotError("unsupported source snapshot schema")
    content = document["content"]
    if not isinstance(content, dict) or set(content) != {"bytes", "sha256"}:
        raise SourceSnapshotError("source snapshot content identity is malformed")
    digest = content["sha256"]
    if (
        not isinstance(content["bytes"], int)
        or isinstance(content["bytes"], bool)
        or content["bytes"] < 0
        or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise SourceSnapshotError("source snapshot content identity is invalid")
    if document["redistribution"] not in {"allowed", "restricted", "unknown"}:
        raise SourceSnapshotError("invalid redistribution status")
    for field in ("id", "canonical_url", "retrieval_url"):
        if not isinstance(document[field], str) or not document[field]:
            raise SourceSnapshotError(f"source snapshot {field} is invalid")
    if not document["canonical_url"].startswith("https://") or not document[
        "retrieval_url"
    ].startswith("https://"):
        raise SourceSnapshotError("source snapshot URLs must use HTTPS")
    for field in ("title", "retrieved_at", "format", "license", "availability", "interpretation"):
        if not isinstance(document[field], str) or not document[field]:
            raise SourceSnapshotError(f"source snapshot {field} is invalid")
    structure = document["structure"]
    normalization = document["normalization"]
    if not isinstance(structure, dict) or not isinstance(normalization, dict):
        raise SourceSnapshotError("source snapshot structure and normalization must be objects")
    if structure:
        structure_keys = {
            "cells", "code_cells", "markdown_cells", "display_data_outputs",
            "execute_result_outputs",
        }
        if set(structure) != structure_keys or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in structure.values()
        ):
            raise SourceSnapshotError("source snapshot structure is malformed")
    source_only_sha256 = None
    if normalization:
        expected = {
            "algorithm", "tool", "removed", "serialization", "source_only_sha256"
        }
        if set(normalization) != expected:
            raise SourceSnapshotError("source snapshot normalization is malformed")
        if normalization["algorithm"] != "jq-cS-strip-runtime-v1":
            raise SourceSnapshotError("unsupported source normalization algorithm")
        if normalization["tool"] != "jq 1.8.1":
            raise SourceSnapshotError("jq normalization must pin version 1.8.1")
        expected_removed = [
            ".cells[].outputs",
            ".cells[].execution_count",
            ".metadata.colab.authorship_tag",
            ".metadata.colab.provenance",
        ]
        if normalization["removed"] != expected_removed:
            raise SourceSnapshotError("source normalization removal set is invalid")
        if normalization["serialization"] != "jq -cS with one trailing LF; not RFC 8785 JCS":
            raise SourceSnapshotError("source normalization serialization is invalid")
        source_only_sha256 = normalization["source_only_sha256"]
        if (
            not isinstance(source_only_sha256, str)
            or len(source_only_sha256) != 64
            or any(character not in "0123456789abcdef" for character in source_only_sha256)
        ):
            raise SourceSnapshotError("source-only identity is invalid")
    return SourceSnapshot(
        id=document["id"],
        size_bytes=content["bytes"],
        sha256=digest,
        canonical_url=document["canonical_url"],
        retrieval_url=document["retrieval_url"],
        redistribution=document["redistribution"],
        structure=structure or None,
        source_only_sha256=source_only_sha256,
    )


def verify_source(snapshot, source_path):
    source_path = Path(source_path)
    digest = hashlib.sha256()
    size = 0
    try:
        with source_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                size += len(chunk)
                digest.update(chunk)
    except OSError as exc:
        raise SourceSnapshotError(f"cannot read source bytes {source_path}: {exc}") from exc
    if size != snapshot.size_bytes or digest.hexdigest() != snapshot.sha256:
        raise SourceSnapshotError(
            f"{snapshot.id}: source identity mismatch: bytes={size}, sha256={digest.hexdigest()}"
        )
    return snapshot


def _normalize_notebook(notebook):
    """Reproduce the pinned jq deletion and compact sorted serialization."""
    normalized = copy.deepcopy(notebook)
    for cell in normalized.get("cells", ()):
        cell.pop("outputs", None)
        cell.pop("execution_count", None)
    colab = normalized.get("metadata", {}).get("colab", {})
    colab.pop("authorship_tag", None)
    colab.pop("provenance", None)
    return (json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ) + "\n").encode("utf-8")


def verify_normalized_source(snapshot, source_path):
    """Verify the recorded jq-compatible normalized notebook identity and structure."""
    if snapshot.source_only_sha256 is None:
        return snapshot
    try:
        notebook = json.loads(Path(source_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceSnapshotError(f"cannot parse notebook source: {exc}") from exc
    cells = notebook.get("cells")
    if not isinstance(cells, list) or any(not isinstance(cell, dict) for cell in cells):
        raise SourceSnapshotError("notebook cells are missing")
    if any(
        not isinstance(cell.get("outputs", []), list)
        or any(not isinstance(output, dict) for output in cell.get("outputs", []))
        for cell in cells
    ):
        raise SourceSnapshotError("notebook outputs are malformed")
    actual_structure = {
        "cells": len(cells),
        "code_cells": sum(cell.get("cell_type") == "code" for cell in cells),
        "markdown_cells": sum(cell.get("cell_type") == "markdown" for cell in cells),
        "display_data_outputs": sum(
            output.get("output_type") == "display_data"
            for cell in cells
            for output in cell.get("outputs", ())
        ),
        "execute_result_outputs": sum(
            output.get("output_type") == "execute_result"
            for cell in cells
            for output in cell.get("outputs", ())
        ),
    }
    if snapshot.structure != actual_structure:
        raise SourceSnapshotError(f"{snapshot.id}: notebook structure mismatch")
    digest = hashlib.sha256(_normalize_notebook(notebook)).hexdigest()
    if digest != snapshot.source_only_sha256:
        raise SourceSnapshotError(f"{snapshot.id}: source-only identity mismatch")
    return snapshot


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fetch_source(snapshot, destination, *, opener=urlopen, timeout=30):
    """Publish a fully verified source atomically; directory durability is best-effort."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        digest = hashlib.sha256()
        size = 0
        try:
            try:
                with opener(snapshot.retrieval_url, timeout=timeout) as response:
                    while chunk := response.read(1024 * 1024):
                        size += len(chunk)
                        if size > snapshot.size_bytes:
                            raise SourceSnapshotError(
                                f"{snapshot.id}: downloaded source exceeds locked size"
                            )
                        digest.update(chunk)
                        temporary.write(chunk)
            except SourceSnapshotError:
                raise
            except (OSError, ValueError) as exc:
                raise SourceSnapshotError(f"{snapshot.id}: source download failed: {exc}") from exc
            temporary.flush()
            os.fsync(temporary.fileno())
            if size != snapshot.size_bytes or digest.hexdigest() != snapshot.sha256:
                raise SourceSnapshotError(f"{snapshot.id}: downloaded source identity mismatch")
            verify_source(snapshot, temporary_path)
            verify_normalized_source(snapshot, temporary_path)
            os.replace(temporary_path, destination)
            try:
                _sync_directory(destination.parent)
            except OSError:
                pass
        finally:
            temporary_path.unlink(missing_ok=True)
    return verify_source(snapshot, destination)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("fetch", "verify"))
    parser.add_argument("manifest")
    parser.add_argument("source")
    args = parser.parse_args(argv)
    snapshot = load_source_snapshot(args.manifest)
    if args.command == "fetch":
        fetch_source(snapshot, args.source)
    else:
        verify_source(snapshot, args.source)
    verify_normalized_source(snapshot, args.source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
