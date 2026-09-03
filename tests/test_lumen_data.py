import io
import json
import hashlib

import pytest

from decluster.lumen_data import (
    LumenValidationError,
    VectorManifest,
    load_explorer_aggregate,
    reconcile_counts,
    summarize_vector_file,
    summarize_vector_stream,
    validate_file_digest,
)


COLUMNS = ("txid", "version", "nsequence")
CSV = "txid,version,nsequence\na,2,Rbf\nb,1,Final\nc,2,Rbf\n"


def test_vector_stream_validates_and_aggregates_axes():
    summary = summarize_vector_stream(io.StringIO(CSV), VectorManifest(COLUMNS, row_count=3))
    assert summary.row_count == 3
    assert summary.axis_counts["version"] == {"2": 2, "1": 1}
    assert summary.axis_counts["nsequence"] == {"Rbf": 2, "Final": 1}
    assert "txid" not in summary.axis_counts


def test_manifest_can_be_loaded_from_json(tmp_path):
    path = tmp_path / "vectors.manifest.json"
    path.write_text(json.dumps({
        "columns": list(COLUMNS), "row_count": 3,
        "start_height": 939969, "end_height": 962721,
        "sha256": "a" * 64,
    }))
    assert VectorManifest.from_json(str(path)) == VectorManifest(
        COLUMNS, 3, 939969, 962721, "a" * 64
    )


def test_file_digest_is_verified(tmp_path):
    path = tmp_path / "vectors.csv"
    path.write_text(CSV)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    validate_file_digest(str(path), digest)
    with pytest.raises(LumenValidationError, match="SHA-256 differs"):
        validate_file_digest(str(path), "0" * 64)


def test_vector_stream_rejects_schema_and_count_mismatches():
    with pytest.raises(LumenValidationError, match="columns differ"):
        summarize_vector_stream(io.StringIO(CSV), VectorManifest(("txid", "nsequence")))
    with pytest.raises(LumenValidationError, match="row count differs"):
        summarize_vector_stream(io.StringIO(CSV), VectorManifest(COLUMNS, row_count=4))


def test_file_range_is_manifest_provenance_not_a_row_field(tmp_path):
    path = tmp_path / "939969-962721.csv"
    path.write_text(CSV)
    manifest = VectorManifest(COLUMNS, 3, 939969, 962721)
    assert summarize_vector_file(str(path), manifest).row_count == 3
    with pytest.raises(LumenValidationError, match="filename range differs"):
        summarize_vector_file(str(path), VectorManifest(COLUMNS, 3, 939969, 962720))


def test_explorer_loader_returns_aggregate_not_transaction_rows(tmp_path):
    path = tmp_path / "explorer-data.json"
    path.write_text(json.dumps({
        "window": {"start_height": 10, "end_height": 20, "epochs": 1},
        "totals": {"txs": 3, "defects": 0},
        "axis_summaries": {
            "version": {"distinct_values": 2, "values": [
                {"value": "1", "count": 1}, {"value": "2", "count": 2}
            ]}
        },
    }))
    aggregate = load_explorer_aggregate(str(path))
    assert aggregate.transaction_count == 3
    assert not hasattr(aggregate, "rows")


def test_reconciliation_reports_delta_without_claiming_its_cause(tmp_path):
    vector = summarize_vector_stream(io.StringIO(CSV), VectorManifest(COLUMNS))
    path = tmp_path / "aggregate.json"
    path.write_text(json.dumps({
        "window": {"start_height": 10, "end_height": 19, "epochs": 1},
        "totals": {"txs": 2, "defects": 0},
        "axis_summaries": {"version": {"distinct_values": 1, "values": [
            {"value": "2", "count": 2}
        ]}},
    }))
    report = reconcile_counts(
        vector, load_explorer_aggregate(str(path)), VectorManifest(COLUMNS, 3, 10, 20)
    )
    assert report["delta"] == 1
    assert report["same_start_height"] is True
    assert report["adjacent_end_height"] is True
    assert report["requires_txid_or_block_evidence"] is True
