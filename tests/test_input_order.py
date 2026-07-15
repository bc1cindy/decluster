"""BIP-69 input/output ordering is n-aware: a small-n sorted set is coincidental (1/n!), so it
must not brand a wallet or forge a same-owner link. Yuval: n=2 -> 1/2, n=3 -> 1/6 (non-negligible),
n>=4 -> <=1/24 (deliberate). The combiner abstains on small-n sorted (like it does on single-input)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.extractors import x_input_order, x_output_order

def _in(txids): return {"vin": [{"txid": t, "vout": 0} for t in txids]}
def _out(vals): return {"vout": [{"value": v} for v in vals]}

def test_input_order_small_n_gate():
    assert x_input_order(_in(["a"])) == "single"
    assert x_input_order(_in(["a", "b"])) == "small_n"           # sorted n=2 -> coincidental (1/2)
    assert x_input_order(_in(["a", "b", "c"])) == "small_n"      # sorted n=3 -> coincidental (1/6)
    assert x_input_order(_in(["a", "b", "c", "d"])) == "bip69"   # sorted n=4 -> deliberate (1/24)
    assert x_input_order(_in(["b", "a", "c", "d"])) == "shuffle" # unsorted -> not BIP-69 (any n)

def test_output_order_small_n_gate():
    assert x_output_order(_out([1, 2])) == "small_n"            # sorted n=2
    assert x_output_order(_out([1, 2, 3, 4])) == "sorted_value" # sorted n=4
    assert x_output_order(_out([2, 1, 3])) == "unsorted"

def _tx(txid, ins, seq=0xfffffffd, lt=0):
    return {"txid": txid, "locktime": lt,
            "vin": [{"txid": fu, "vout": 0, "sequence": seq, "prevout": {"value": 100000}} for fu in ins],
            "vout": [{"value": 50000}]}

def test_combiner_abstains_on_small_n_sorted():
    from decluster.combiner import Combiner
    cmb = Combiner.from_library()
    # two coincidentally-sorted 2-input txs -> in_order must NOT contribute a same-owner link
    _t, rows = cmb.score(_tx("A", ["x", "y"]), _tx("B", ["p", "q"]), explain=True)
    io = [r for r in rows if r[0] == "in_order"][0]
    assert io[1] == "small_n" and io[3] is None, "small-n sorted -> in_order abstains (no false link)"
    # two 4-input BIP-69 txs -> in_order DOES contribute the software-rarity link
    _t2, rows2 = cmb.score(_tx("A4", ["a", "b", "c", "d"]), _tx("B4", ["e", "f", "g", "h"]), explain=True)
    io2 = [r for r in rows2 if r[0] == "in_order"][0]
    assert io2[1] == "bip69" and io2[3] is not None and io2[3] > 0, "n>=4 BIP-69 -> same-owner link kept"

def test_combiner_bip69_vs_shuffle_is_negative():
    # mismatch path: a BIP-69 tx vs a shuffle tx are DIFFERENT wallets -> negative weight.
    # (regression guard: a 0-bit abstain value must not poison the collision -> +bits.)
    from decluster.combiner import Combiner
    cmb = Combiner.from_library()
    assert cmb.collision["in_order"] < 0.95, "collision must stay < consistency (no 0-bit poisoning)"
    _t, rows = cmb.score(_tx("A", ["a", "b", "c", "d"]), _tx("B", ["d", "c", "b", "a"]), explain=True)
    io = [r for r in rows if r[0] == "in_order"][0]
    assert (io[1], io[2]) == ("bip69", "shuffle")
    assert io[3] is not None and io[3] < 0, f"bip69 vs shuffle -> DIFFERENT wallet -> negative (got {io[3]:+.2f})"

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
