import json

import pytest

from decluster.boltzmann_fee_snapshot import build_snapshot


def _transaction(txid, inputs, outputs):
    return {
        "txid": txid,
        "vin": [{"prevout": {"value": value}} for value in inputs],
        "vout": [{"value": value} for value in outputs],
    }


def test_snapshot_selects_exact_population_and_is_deterministic(tmp_path):
    source = tmp_path / "source.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    rows = [
        _transaction("single", [3], [2]),
        _transaction("kept-1", [3, 2], [4]),
        _transaction("large", [1, 2, 3], [1, 2, 3]),
        _transaction("kept-2", [5, 4], [8]),
    ]
    source.write_text(json.dumps(rows), encoding="utf-8")

    assert build_snapshot(source, first, cap=2, max_coins=4) == 2
    assert build_snapshot(source, second, cap=2, max_coins=4) == 2
    assert first.read_bytes() == second.read_bytes()
    assert [row["txid"] for row in json.loads(first.read_text())] == [
        "kept-1",
        "kept-2",
    ]


def test_snapshot_refuses_incomplete_population(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(json.dumps([_transaction("one", [2, 1], [2])]))

    with pytest.raises(ValueError, match="only 1 eligible"):
        build_snapshot(source, tmp_path / "output.json", cap=2)
