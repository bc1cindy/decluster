"""`catalog/lumen-vectors-2026.json` is the declared identity of the Lumen vector artifact, which
this checkout does not hold (4 GiB, zstd CSV). These tests wire the catalog to
`decluster.lumen_data`'s schema contract, so a drift in either — a renamed manifest field, a
changed column requirement, an edited catalog — fails loudly instead of being discovered the next
time someone has the artifact.

Nothing here fabricates artifact content. The row count is read from the catalog as a *declaration*;
the only bytes actually hashed are the committed explorer fixture.
"""
import hashlib
import json
from pathlib import Path

import pytest

from decluster.lumen_data import (
    TXID_COLUMN,
    VectorManifest,
    VectorSummary,
    load_explorer_aggregate,
    reconcile_counts,
    validate_filename_range,
)

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog" / "lumen-vectors-2026.json"
EXPLORER_FIXTURE = ROOT / "tests" / "fixtures" / "lumen_explorer_data.json"


@pytest.fixture(scope="module")
def catalog():
    with CATALOG.open(encoding="utf-8") as stream:
        return json.load(stream)


def test_catalog_entry_parses_as_a_vector_manifest(catalog):
    manifest = VectorManifest.from_mapping(catalog)
    assert manifest.columns[0] == TXID_COLUMN, "summarize_vector_stream requires a leading txid"
    assert len(set(manifest.columns)) == len(manifest.columns)
    assert manifest.row_count == catalog["row_count"]
    assert manifest.sha256 == catalog["sha256"]


def test_catalog_filename_agrees_with_its_declared_block_range(catalog):
    """The vector rows carry no height column, so the filename is the only provenance the loader
    can check the declared range against."""
    validate_filename_range(catalog["artifact"], VectorManifest.from_mapping(catalog))


def test_catalog_comparison_aggregate_matches_the_committed_fixture(catalog):
    comparison = catalog["comparison_aggregate"]
    digest = hashlib.sha256(EXPLORER_FIXTURE.read_bytes()).hexdigest()
    assert digest == comparison["fixture_sha256"]

    aggregate = load_explorer_aggregate(str(EXPLORER_FIXTURE))
    assert aggregate.transaction_count == comparison["transaction_count"]
    assert aggregate.start_height == comparison["start_height"]
    assert aggregate.end_height == comparison["end_height"]


def test_the_recorded_delta_is_still_unreconciled(catalog):
    """`reconcile_counts` describes the discrepancy and refuses to attribute it. The catalog says
    the same in words; this pins that the two agree, including that adjacent end heights are
    reported as a coincidence to be explained, not as the explanation."""
    manifest = VectorManifest.from_mapping(catalog)
    aggregate = load_explorer_aggregate(str(EXPLORER_FIXTURE))
    declared = VectorSummary(manifest.row_count, manifest.columns, {})

    result = reconcile_counts(declared, aggregate, manifest)

    assert result["delta"] == catalog["comparison_aggregate"]["delta"] == 6219
    assert result["same_start_height"] is True
    assert result["adjacent_end_height"] is True
    assert result["requires_txid_or_block_evidence"] is True
    assert catalog["comparison_aggregate"]["status"].startswith("unreconciled")
