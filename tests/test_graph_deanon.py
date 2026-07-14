"""graph_deanon probe tests (offline, synthetic)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _tx(ins, outs):
    return ({"vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
             "vout": [{"scriptpubkey_address": a} for a in outs]}, 0)


def test_detects_signal_and_shuffle_null():
    from decluster.graph_deanon import evaluate
    # two entities, each with its own hubs -> structure predicts same-owner
    s = [_tx(["a1", "a2"], ["hA1", "hA2"]), _tx(["a2", "a3"], ["hA1", "hA3"]),
         _tx(["a1"], ["hA1"]), _tx(["a3"], ["hA2"]),
         _tx(["b1", "b2"], ["hB1", "hB2"]), _tx(["b2", "b3"], ["hB1", "hB3"]),
         _tx(["b1"], ["hB1"]), _tx(["b3"], ["hB2"])]
    r = evaluate(s)
    assert r["auc_full"] > 0.9, r["auc_full"]
    assert r["auc_payment"] > 0.5, r["auc_payment"]
    assert 0.3 < r["auc_shuffle"] < 0.7, r["auc_shuffle"]


def test_payment_graph_excludes_cospend():
    from decluster.graph_deanon import build
    _, full, pay, _ = build([_tx(["x", "y"], ["z"])])
    assert "y" in full["x"]                # co-inputs are neighbors in full
    assert "y" not in pay.get("x", set())  # but not in payment-only
    assert "z" in pay["x"]                 # input->output edge kept


def test_depth_recovers_churn():
    # same-owner linked only at 2 hops (distinct counterparties) -> k=1 blind, k>=2 recovers
    from decluster.graph_deanon import analyze
    s = []
    for n in range(30):  # size-3 cluster: a1-a3 is the transitive held-out pair
        a1, a2, a3 = "e%d_a" % n, "e%d_b" % n, "e%d_c" % n
        c1, c3 = "e%d_c1" % n, "e%d_c3" % n
        s += [_tx([a1, a2], ["e%d_o1" % n]),
              _tx([a2, a3], ["e%d_o2" % n]),     # co-spends => a1,a3 transitive
              _tx([a1], [c1]), _tx([a3], [c3]),  # distinct counterparties (k=1 blind)
              _tx([c1], [c3])]                   # c1-c3 linked => a1,a3 at 2 hops
    r = analyze(s, ks=(1, 2, 3))
    assert r["aucs"][0] < r["aucs"][2], r["aucs"]   # depth recovers signal


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
