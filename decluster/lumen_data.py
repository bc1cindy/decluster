"""Streaming ingestion and validation for Lumen fingerprint artifacts.

The transaction CSV and explorer JSON deliberately have different types: the former contains
one fingerprint vector per transaction, while the latter contains only aggregate statistics.
Keeping their loaders separate prevents aggregate data from accidentally being used as records.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Mapping, Optional, Sequence, TextIO, Tuple


TXID_COLUMN = "txid"
_RANGE_RE = re.compile(r"(?P<start>\d+)-(?P<end>\d+)\.csv(?:\.zst)?$")


class LumenValidationError(ValueError):
    """A Lumen artifact does not satisfy its declared manifest."""


@dataclass(frozen=True)
class VectorManifest:
    """Expected identity and shape of a transaction-level vector artifact."""

    columns: Tuple[str, ...]
    row_count: Optional[int] = None
    start_height: Optional[int] = None
    end_height: Optional[int] = None
    sha256: Optional[str] = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "VectorManifest":
        columns = value.get("columns")
        if not isinstance(columns, (list, tuple)) or not all(isinstance(x, str) for x in columns):
            raise LumenValidationError("manifest 'columns' must be a list of strings")
        return cls(
            tuple(columns),
            _optional_int(value, "row_count"),
            _optional_int(value, "start_height"),
            _optional_int(value, "end_height"),
            _optional_sha256(value),
        )

    @classmethod
    def from_json(cls, path: str) -> "VectorManifest":
        with open(path, encoding="utf-8") as stream:
            value = json.load(stream)
        if not isinstance(value, dict):
            raise LumenValidationError("vector manifest must be a JSON object")
        return cls.from_mapping(value)


@dataclass(frozen=True)
class VectorSummary:
    row_count: int
    columns: Tuple[str, ...]
    axis_counts: Mapping[str, Counter]


@dataclass(frozen=True)
class ExplorerAggregate:
    """Validated aggregate survey data; it intentionally exposes no row iterator."""

    start_height: int
    end_height: int
    epochs: int
    transaction_count: int
    defects: int
    axis_summaries: Mapping[str, object]


def _optional_int(value: Mapping[str, object], key: str) -> Optional[int]:
    item = value.get(key)
    if item is None:
        return None
    if isinstance(item, bool) or not isinstance(item, int):
        raise LumenValidationError(f"manifest {key!r} must be an integer")
    return item


def _optional_sha256(value: Mapping[str, object]) -> Optional[str]:
    digest = value.get("sha256")
    if digest is None:
        return None
    if (not isinstance(digest, str) or len(digest) != 64 or
            any(ch not in "0123456789abcdef" for ch in digest)):
        raise LumenValidationError("manifest 'sha256' must be a lowercase SHA-256 hex digest")
    return digest


def validate_file_digest(path: str, expected_sha256: str, chunk_size=1024 * 1024) -> None:
    """Hash the stored artifact bytes and reject a provenance mismatch."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        raise LumenValidationError(
            f"artifact SHA-256 differs: expected {expected_sha256}, got {actual}"
        )


@contextmanager
def open_vector_text(path: str) -> Iterator[TextIO]:
    """Open plain CSV or zstd CSV as a text stream without materialising decompressed data."""

    source = Path(path)
    if source.suffix != ".zst":
        with source.open("r", encoding="utf-8", newline="") as stream:
            yield stream
        return

    try:
        import zstandard  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "reading .zst vectors requires the optional 'zstandard' package"
        ) from exc

    with source.open("rb") as compressed:
        decompressor = zstandard.ZstdDecompressor()
        with decompressor.stream_reader(compressed) as binary:
            with io.TextIOWrapper(binary, encoding="utf-8", newline="") as stream:
                yield stream


def iter_vector_rows(stream: TextIO, expected_columns: Sequence[str]) -> Iterator[Dict[str, str]]:
    """Yield CSV rows and reject missing, reordered, duplicate, or surplus columns."""

    reader = csv.DictReader(stream)
    actual = tuple(reader.fieldnames or ())
    expected = tuple(expected_columns)
    if actual != expected:
        raise LumenValidationError(f"CSV columns differ: expected {expected!r}, got {actual!r}")
    if len(set(actual)) != len(actual):
        raise LumenValidationError("CSV header contains duplicate columns")
    for line_number, row in enumerate(reader, 2):
        if None in row or any(value is None for value in row.values()):
            raise LumenValidationError(f"malformed CSV row at line {line_number}")
        yield row  # one row is live at a time unless the caller retains it


def validate_filename_range(path: str, manifest: VectorManifest) -> None:
    """Check declared heights against a conventional ``START-END.csv.zst`` filename.

    Vector rows have no height column, so this validates artifact provenance rather than making an
    unsupported claim that heights were derived from CSV content.
    """

    if manifest.start_height is None and manifest.end_height is None:
        return
    match = _RANGE_RE.search(Path(path).name)
    if match is None:
        raise LumenValidationError("cannot validate block range: filename has no START-END range")
    actual = (int(match.group("start")), int(match.group("end")))
    expected = (manifest.start_height, manifest.end_height)
    if actual != expected:
        raise LumenValidationError(f"filename range differs: expected {expected}, got {actual}")


def summarize_vector_stream(stream: TextIO, manifest: VectorManifest) -> VectorSummary:
    """Validate and aggregate a vector CSV in one pass using memory proportional to cardinality."""

    if not manifest.columns or manifest.columns[0] != TXID_COLUMN:
        raise LumenValidationError("transaction vector schema must begin with 'txid'")
    counts = {axis: Counter() for axis in manifest.columns[1:]}
    row_count = 0
    for row in iter_vector_rows(stream, manifest.columns):
        row_count += 1
        for axis, counter in counts.items():
            counter[row[axis]] += 1
    if manifest.row_count is not None and row_count != manifest.row_count:
        raise LumenValidationError(
            f"CSV row count differs: expected {manifest.row_count}, got {row_count}"
        )
    return VectorSummary(row_count, manifest.columns, counts)


def summarize_vector_file(path: str, manifest: VectorManifest, *, verify_digest=True) -> VectorSummary:
    validate_filename_range(path, manifest)
    if verify_digest and manifest.sha256 is not None:
        validate_file_digest(path, manifest.sha256)
    with open_vector_text(path) as stream:
        return summarize_vector_stream(stream, manifest)


def load_explorer_aggregate(path: str) -> ExplorerAggregate:
    """Load and internally validate Lumen's aggregate explorer artifact."""

    with open(path, encoding="utf-8") as stream:
        value = json.load(stream)
    try:
        window = value["window"]
        totals = value["totals"]
        axes = value["axis_summaries"]
        total = int(totals["txs"])
        result = ExplorerAggregate(
            int(window["start_height"]), int(window["end_height"]), int(window["epochs"]),
            total, int(totals["defects"]), axes,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LumenValidationError("invalid explorer aggregate schema") from exc
    if not isinstance(axes, dict):
        raise LumenValidationError("axis_summaries must be an object")
    for axis, summary in axes.items():
        try:
            values = summary["values"]
            count = sum(int(item["count"]) for item in values)
            distinct = int(summary["distinct_values"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LumenValidationError(f"invalid explorer summary for axis {axis!r}") from exc
        if count != total or distinct != len(values):
            raise LumenValidationError(f"inconsistent explorer summary for axis {axis!r}")
    return result


def reconcile_counts(
    vectors: VectorSummary,
    explorer: ExplorerAggregate,
    vector_manifest: Optional[VectorManifest] = None,
) -> Mapping[str, object]:
    """Describe, but do not guess the cause of, a vector/aggregate count discrepancy."""

    delta = vectors.row_count - explorer.transaction_count
    same_start = None
    adjacent_end = None
    if vector_manifest is not None:
        if vector_manifest.start_height is not None:
            same_start = vector_manifest.start_height == explorer.start_height
        if vector_manifest.end_height is not None:
            adjacent_end = vector_manifest.end_height == explorer.end_height + 1
    return {
        "vector_rows": vectors.row_count,
        "aggregate_transactions": explorer.transaction_count,
        "delta": delta,
        "same_start_height": same_start,
        "adjacent_end_height": adjacent_end,
        "requires_txid_or_block_evidence": delta != 0,
    }
