"""merged transaction demo tests (offline + 1 live, with skip)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_from_library_bits():
    from decluster.combiner import Combiner
    from decluster import library
    c = Combiner.from_library()
    freq = {a[0]: a[2] for a in c.axes}         # axes: (name, fn, p, collision, abstain)
    collision = {a[0]: a[3] for a in c.axes}
    # freq = 2**-bits, sourced from the current library (recalibration-proof)
    assert abs(freq["nsequence"]["rbf_fffffffd"]
               - 2 ** -library.bits("nsequence", "rbf_fffffffd")) < 1e-6
    # locktime coarsened by the combiner: zero + aggregated height_*
    assert set(freq["locktime"]) == {"zero", "height"}
    lb = library._BY["locktime"]["bits"]
    exp_height = sum(2 ** -b for v, b in lb.items() if v != "zero")
    assert abs(freq["locktime"]["height"] - exp_height) < 1e-6
    # collision is sum of squares
    assert abs(collision["locktime"]
               - sum(p*p for p in freq["locktime"].values())) < 1e-9

def test_merge_money_shot():
    from decluster import fetch_tx
    from decluster.combiner import Combiner
    from decluster.cluster import cluster_refined
    MERGE = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"
    CAKE    = "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729"
    SENDER  = "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"
    cache = os.path.join(os.path.dirname(__file__), "..", ".cache", CAKE + ".json")
    if not os.path.exists(cache):
        try: fetch_tx(CAKE)
        except Exception: print("SKIP: offline"); return
    nodes = {MERGE, CAKE, SENDER}
    nodes.add(fetch_tx(CAKE)["vin"][0]["txid"])
    for v in fetch_tx(SENDER)["vin"]: nodes.add(v["txid"])
    cmb = Combiner.from_library()
    s = cmb.score(fetch_tx(SENDER), fetch_tx(CAKE))
    assert s < 0, f"sender/Cake should be refused, got {s:+.2f}"
    groups, refused, linked = cluster_refined(nodes, cmb, amount=False)
    for g in groups:
        assert not (SENDER in g and CAKE in g), "sender and Cake must be split"
    assert linked, "expected added links the co-spend missed"

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
