import gzip
import json

import pytest

from decluster.ns_bitcoin_snapshot import build_window


def _write_records(path):
    with gzip.open(path, "wt", encoding="utf-8") as target:
        for height in (9, 10, 11, 12, 13):
            target.write(json.dumps({"height": height, "txid": str(height)}) + "\n")


def test_builder_filters_inclusively_and_is_byte_deterministic(tmp_path):
    source = tmp_path / "source.ndjson.gz"
    first = tmp_path / "first.ndjson.gz"
    second = tmp_path / "second.ndjson.gz"
    _write_records(source)

    assert build_window(source, first, minimum_height=10, maximum_height=12) == 3
    assert build_window(source, second, minimum_height=10, maximum_height=12) == 3
    assert first.read_bytes() == second.read_bytes()
    with gzip.open(first, "rt", encoding="utf-8") as records:
        assert [json.loads(line)["height"] for line in records] == [10, 11, 12]


def test_builder_rejects_an_inverted_range(tmp_path):
    with pytest.raises(ValueError, match="must not exceed"):
        build_window(
            tmp_path / "unused.gz",
            tmp_path / "output.gz",
            minimum_height=2,
            maximum_height=1,
        )
