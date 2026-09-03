import gzip
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "examples" / "split_epochs.py"
SPEC = importlib.util.spec_from_file_location("split_epochs", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_split_file_streams_sorted_chunks_and_hashes_them(tmp_path):
    source = tmp_path / "month.ndjson.gz"
    with gzip.open(source, "wt") as f:
        for height in (10, 11, 12, 13, 14):
            f.write(json.dumps({"height": height, "vin": [], "vout": []}) + "\n")
    records = MOD.split_file(source, tmp_path, blocks=2)
    assert [r["transactions"] for r in records] == [2, 2, 1]
    assert all(len(r["sha256"]) == 64 for r in records)
    heights = []
    for record in records:
        with gzip.open(record["path"], "rt") as f:
            heights.extend(json.loads(line)["height"] for line in f)
    assert heights == [10, 11, 12, 13, 14]


def test_split_file_accepts_unsorted_paginated_input(tmp_path):
    source = tmp_path / "bad.ndjson"
    source.write_text('{"height": 2}\n{"height": 1}\n')
    records = MOD.split_file(source, tmp_path, blocks=2)
    assert sum(record["transactions"] for record in records) == 2
