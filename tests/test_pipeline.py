"""Pipeline sanity tests."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster import fetch_tx
from decluster.extractors import x_nsequence, x_input_order
from decluster.combiner import Combiner

MERGE = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"
CAKE   ="0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729"
SENDER ="91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"

def test_extractor_cake_signature():
    # Cake coin: 1-in seq=0x01 -> lone 0x01 (ambiguous, not the strict group-C pattern)
    assert x_nsequence(fetch_tx(CAKE)) == "seq_0x01_other"
    # sender coin: 3-in all MAX
    assert x_nsequence(fetch_tx(SENDER)) == "max_ffffffff"

def test_merge_is_intra_uniform():
    # the merged transaction tx itself is clean: both inputs rbf_fffffffd
    assert x_nsequence(fetch_tx(MERGE)) == "rbf_fffffffd"

def test_combiner_separates_and_links():
    cmb = Combiner()
    diff = cmb.score(fetch_tx(CAKE), fetch_tx(SENDER))      # merged transaction: donos diferentes
    be2e = fetch_tx(CAKE)["vin"][0]["txid"]
    same = cmb.score(fetch_tx(CAKE), fetch_tx(be2e))        # Cake lineage: same owner
    assert diff < -2, f"esperado <-2 bits, got {diff:.2f}"
    assert same > +3, f"esperado >+3 bits, got {same:.2f}"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("all tests passed")
