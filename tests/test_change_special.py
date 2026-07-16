"""Special-case change labelers. label_optimal_change reads ONLY values (the anti-circularity
property, encoded as test_optimal_change_reads_only_values)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.change_special import label_optimal_change, label_address_reuse, build_gt_special

def _tx(txid="T", in_vals=(100, 200), out_vals=(50, 500), in_addrs=("A", "B"), out_addrs=("c", "d"),
        seq=0xFFFFFFFD, ver=2, lt=0):
    return {"txid": txid, "locktime": lt, "version": ver,
            "vin": [{"txid": "f", "vout": 0, "sequence": seq,
                     "prevout": {"value": v, "scriptpubkey_address": a}}
                    for v, a in zip(in_vals, in_addrs)],
            "vout": [{"value": v, "scriptpubkey_address": a} for v, a in zip(out_vals, out_addrs)]}

def test_optimal_change_basic():
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500))) == 0   # 50 < min(100)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(500, 50))) == 1   # tracks value

def test_optimal_change_needs_two_inputs():
    assert label_optimal_change(_tx(in_vals=(100,), out_vals=(50, 500))) is None

def test_optimal_change_not_decisive():
    # both outputs below the smallest input -> can't single out the change
    assert label_optimal_change(_tx(in_vals=(1000, 2000), out_vals=(50, 60))) is None
    # neither output below the smallest input -> None
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(150, 500))) is None

def test_optimal_change_missing_values():
    tx = _tx(in_vals=(100, 200), out_vals=(50, 500)); del tx["vin"][0]["prevout"]["value"]
    del tx["vin"][1]["prevout"]["value"]
    assert label_optimal_change(tx) is None

def test_optimal_change_reads_only_values():
    base = label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500))) ; assert base == 0
    # rewrite ALL addresses -> label unchanged (disjoint from addresses / co-spend)
    assert label_optimal_change(_tx(in_addrs=("X", "Y"), out_addrs=("z", "w"),
                                    in_vals=(100, 200), out_vals=(50, 500))) == base
    # junk nSequence/version/locktime -> label unchanged (disjoint from those fingerprints)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(50, 500),
                                    seq=0x01, ver=1, lt=800000)) == base
    # change a value so nothing is < min input -> label drops (value-sensitive)
    assert label_optimal_change(_tx(in_vals=(100, 200), out_vals=(150, 500))) is None

def test_address_reuse():
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("A", "d"))) == 0   # output0 == input A
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("c", "d"))) is None
    assert label_address_reuse(_tx(in_addrs=("A", "B"), out_addrs=("A", "B"))) is None  # both -> None

def test_build_gt_special():
    keep = _tx("K", in_vals=(100, 200), out_vals=(50, 500))     # optimal-change -> 0
    drop = _tx("D", in_vals=(100,), out_vals=(50, 500))         # 1 input -> None
    assert build_gt_special([keep, drop], label_optimal_change) == [{"tx": keep, "change_index": 0}]

def test_within_tx_rates_concrete():
    from decluster.change_special import within_tx_rates
    # round_number picks the less-round output; label is optimal-change.
    # tx K: inputs (100,200), outputs (50, 500) -> optimal-change = 0; 50 is less round than 500 -> round_number=0 (agree)
    K = _tx("K", in_vals=(100, 200), out_vals=(50, 500))
    gt = [{"tx": K, "change_index": 0}]
    rates = within_tx_rates(gt)
    assert rates["round_number"] == (1.0, 0.0, 1.0)          # agrees on the single record
    assert set(rates) == {"round_number", "address_reuse"}

def test_optimal_change_partial_missing_input_value():
    tx = _tx(in_vals=(100, 200), out_vals=(50, 500))
    del tx["vin"][1]["prevout"]["value"]        # one input value missing -> min() untrustworthy
    assert label_optimal_change(tx) is None

def test_label_agreement():
    from decluster.change_special import label_agreement
    def rec(txid, ci): return {"tx": {"txid": txid}, "change_index": ci}
    a = [rec("T1", 0), rec("T2", 1), rec("T3", 0)]        # T1,T2,T3
    b = [rec("T1", 0), rec("T2", 0), rec("T4", 1)]        # T1 agree, T2 disagree, T4 only_b
    assert label_agreement(a, b) == {"both": 2, "agree": 1, "disagree": 1, "only_a": 1, "only_b": 1}

def test_round_number_basic():
    from decluster.change_special import label_round_number
    # out0 = 5_000_000 sats (0.05 BTC, round at d=3); out1 = 4_321 (not round) -> change = out1
    assert label_round_number(_tx(out_vals=(5_000_000, 4_321))) == 1
    assert label_round_number(_tx(out_vals=(4_321, 5_000_000))) == 0   # tracks which output is round

def test_round_number_threshold_edge():
    from decluster.change_special import label_round_number
    # d=3 -> unit = 10**5 = 100_000. 100_000 is round; 100_001 is not -> change = the non-round (1)
    assert label_round_number(_tx(out_vals=(100_000, 100_001)), d=3) == 1

def test_round_number_abstains():
    from decluster.change_special import label_round_number
    assert label_round_number(_tx(out_vals=(100_000, 200_000)), d=3) is None   # both round
    assert label_round_number(_tx(out_vals=(12_345, 67_891)), d=3) is None      # neither round

def test_round_number_reads_only_values():
    from decluster.change_special import label_round_number
    base = label_round_number(_tx(out_vals=(5_000_000, 4_321))); assert base == 1
    # rewrite addresses + nSequence/version/locktime -> unchanged (values-only, disjoint fingerprints)
    assert label_round_number(_tx(out_vals=(5_000_000, 4_321), in_addrs=("X", "Y"),
                                  out_addrs=("z", "w"), seq=0x01, ver=1, lt=800000)) == base

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns: fn(); print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
