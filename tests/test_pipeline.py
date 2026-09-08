"""Offline pipeline sanity tests over the committed merged-anchor fixture."""
import json
from pathlib import Path

from decluster.extractors import x_nsequence, x_input_order
from decluster.combiner import Combiner

FIXTURE = Path(__file__).parent / "fixtures" / "merged_anchor_931d6627.json"


def transactions():
    return json.loads(FIXTURE.read_text())["transactions"]

def test_extractor_cake_signature():
    txs = transactions()
    # Cake coin: 1-in seq=0x01 -> lone 0x01 (ambiguous, not the strict group-C pattern)
    assert x_nsequence(txs["cake"]) == "seq_0x01_other"
    # sender coin: 3-in all MAX
    assert x_nsequence(txs["sender"]) == "max_ffffffff"

def test_merge_is_intra_uniform():
    # the merged transaction tx itself is clean: both inputs rbf_fffffffd
    merged = {"vin": [{"sequence": 0xFFFFFFFD}, {"sequence": 0xFFFFFFFD}]}
    assert x_nsequence(merged) == "rbf_fffffffd"

def test_combiner_separates_and_links():
    txs = transactions()
    cmb = Combiner.from_library()
    diff = cmb.score(txs["cake"], txs["sender"])
    cake_lineage = {
        "locktime": 0,
        "vin": [{
            "sequence": 1,
            "txid": "92a2c97f398cd7672e6a9f5d15e0f3523ba47483c916f6c84d397d9159e6f8eb",
            "vout": 0,
        }],
    }
    same = cmb.score(txs["cake"], cake_lineage)
    assert diff < -2, f"esperado <-2 bits, got {diff:.2f}"
    assert same > +3, f"esperado >+3 bits, got {same:.2f}"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("all tests passed")
