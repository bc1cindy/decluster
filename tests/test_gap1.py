"""amount subtransaction re-partition inference"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def _merge_931d():
    # real 931d6627 values: sender in 2000, Cake in 5750; outs 791, 6750; fee 209
    return {"txid": "931d",
            "vin": [{"txid": "sender", "prevout": {"value": 2000}},
                    {"txid": "cake",   "prevout": {"value": 5750}}],
            "vout": [{"value": 791}, {"value": 6750}]}

def test_subtransactions_931d():
    from decluster.subtransaction import subtransactions
    ranked, amb = subtransactions(_merge_931d())
    # two assignments have output>input (1000 and 4750) -> 1 bit ambiguity
    assert amb == 1.0
    # roundness picks payment 1000 (round) over 4750
    payment, score, ri, ro = ranked[0]
    assert payment == 1000 and ri == 1 and ro == 1   # receiver = Cake input(1) -> output(1)

def test_partition_signal_931d():
    from decluster.subtransaction import partition_signal
    sig = partition_signal(_merge_931d())
    # amount says the two inputs are DIFFERENT owners (refuse the common-input merge)
    assert ("sender", "cake") in sig["refuse"] or ("cake", "sender") in sig["refuse"]
    assert sig["payment"] == 1000
    # each input linked to its own output
    assert ("cake", "931d:1") in sig["link"]
    assert ("sender", "931d:0") in sig["link"]

def test_roundness():
    from decluster.subtransaction import roundness
    assert roundness(1000) == 3
    assert roundness(4750) == 1
    assert roundness(0) == 0

def test_scope_guard():
    from decluster.subtransaction import subtransactions
    tx = {"txid": "x", "vin": [{"txid": "a", "prevout": {"value": 1}}],
          "vout": [{"value": 1}]}  # 1-in/1-out
    assert subtransactions(tx) == ([], None)

def test_amount_refuse_weight_931d():
    from decluster.cluster import amount_refuse_weight
    PAY  = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"
    CAKE = "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729"
    SEND = "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"
    import os
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".cache", CAKE + ".json")):
        try:
            from decluster import fetch_tx; fetch_tx(CAKE)
        except Exception: print("SKIP: offline"); return
    w = amount_refuse_weight(PAY, SEND, CAKE)
    assert w < 0, f"amount should push toward refusal, got {w}"   # roundness margin 3-1=2 -> -2

def test_cluster_fused_refuses_merge():
    from decluster import fetch_tx
    from decluster.combiner import Combiner
    from decluster.cluster import cluster_fused
    import os
    PAY  = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"
    CAKE = "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729"
    SEND = "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", ".cache", CAKE + ".json")):
        try: fetch_tx(CAKE)
        except Exception: print("SKIP: offline"); return
    nodes = {PAY, CAKE, SEND}
    nodes.add(fetch_tx(CAKE)["vin"][0]["txid"])
    for v in fetch_tx(SEND)["vin"]: nodes.add(v["txid"])
    groups, refused, linked = cluster_fused(nodes, Combiner.from_library())
    # sender and Cake are split
    for g in groups:
        assert not (SEND in g and CAKE in g)
    # the sender<->Cake refusal is recorded with BOTH a fingerprint and an amount term
    r = [x for x in refused if set(x[:2]) == {SEND, CAKE}]
    assert r, "sender/Cake refusal not recorded"
    a, b, t, fp, amt, total = r[0]
    assert amt < 0 and fp < 0 and total <= fp   # amount deepens the fingerprint refusal

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("6 passed")
