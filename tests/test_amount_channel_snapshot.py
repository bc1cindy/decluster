import json

import pytest

from decluster.amount_channel_snapshot import build_snapshot


def test_snapshot_normalizes_numbers_and_is_deterministic(tmp_path):
    source = tmp_path / "source.ndjson"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    source.write_text(
        "\n".join([
            json.dumps({"txid": "a", "height": "2", "vin": [], "vout": []}),
            json.dumps({"txid": "b", "height": "1", "vin": [], "vout": []}),
        ])
    )

    assert build_snapshot(source, first, expected_records=2) == 2
    assert build_snapshot(source, second, expected_records=2) == 2
    assert first.read_bytes() == second.read_bytes()
    rows = json.loads(first.read_text())
    assert [row["txid"] for row in rows] == ["a", "b"]
    assert [row["height"] for row in rows] == [2, 1]


def test_snapshot_rejects_an_unexpected_population(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("[]")

    with pytest.raises(ValueError, match="expected 1 transactions, found 0"):
        build_snapshot(source, tmp_path / "output.json", expected_records=1)
