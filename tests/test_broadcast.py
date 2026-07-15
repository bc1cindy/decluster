"""broadcast-time estimator + locktime_vs_broadcast axis (pure, offline)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.broadcast import tx_feerate, broadcast_window

def test_tx_feerate():
    assert tx_feerate({"fee": 1000, "weight": 400}) == 10.0   # 1000 / (400/4)
    assert tx_feerate({"fee": 0, "weight": 400}) is None       # coinbase / no fee
    assert tx_feerate({"weight": 400}) is None

def test_broadcast_window_tight():
    # block N-1's cheapest (5) is below T's feerate (10) -> T wasn't available at N-1
    assert broadcast_window(10.0, 5.0, 100, 700) == (True, 100, 700)

def test_broadcast_window_loose():
    # N-1's cheapest (12) >= T's feerate (10) -> T could have been waiting
    assert broadcast_window(10.0, 12.0, 100, 700) == (False, None, 700)

def test_broadcast_window_none():
    assert broadcast_window(None, 5.0, 100, 700) is None       # coinbase
    assert broadcast_window(10.0, None, 100, 700) == (False, None, 700)  # unknown prev_min

from decluster.broadcast import locktime_vs_broadcast
from decluster.extractors import x_locktime_vs_broadcast

def test_axis_values():
    tight = (True, 100, 700)
    loose = (False, None, 700)
    assert locktime_vs_broadcast(0, 900, tight) == "no_locktime"
    assert locktime_vs_broadcast(500_000_001, 900, tight) == "timestamp"
    assert locktime_vs_broadcast(899, 900, tight) == "matches"       # ~ current tip
    assert locktime_vs_broadcast(700, 900, tight) == "backdated"     # >100 below N
    assert locktime_vs_broadcast(950, 900, tight) == "future"        # above N
    assert locktime_vs_broadcast(899, 900, loose) == "na_loose"      # height but loose
    assert locktime_vs_broadcast(899, 900, None) == "na_loose"

def test_extractor_reads_annotation():
    tx = {"fee": 1000, "weight": 400, "locktime": 899,
          "status": {"block_height": 900, "block_time": 700},
          "_bc": {"prev_min": 5.0, "prev_time": 100, "incl_time": 700}}
    assert x_locktime_vs_broadcast(tx) == "matches"
    assert x_locktime_vs_broadcast({"locktime": 0}) == "na"          # not annotated

from decluster.broadcast import annotate_broadcast

def test_annotate():
    txs = [{"status": {"block_height": 900, "block_time": 700}},
           {"status": {"block_height": 900, "block_time": 700}},   # shares block 900
           {"status": {}}]                                          # unconfirmed -> skipped
    calls = []
    def fake_hash(h): calls.append(h); return f"hash{h}"
    def fake_block(bid): return {"timestamp": 100, "extras": {"feeRange": [5.0, 9, 20]}}
    annotate_broadcast(txs, fake_hash, fake_block)
    assert txs[0]["_bc"] == {"prev_min": 5.0, "prev_time": 100, "incl_time": 700}
    assert txs[1]["_bc"] == txs[0]["_bc"]
    assert "_bc" not in txs[2]
    assert calls == [899]                                           # block 899 fetched once (cached)

from decluster.engine import locktime_class

def test_deconfounds_plain_locktime():
    # A tx that WAITED (loose bound): the plain locktime axis (vs inclusion height) misreads it
    # as heavily backdated; the broadcast axis abstains (na_loose), refusing that verdict.
    tx = {"fee": 200, "weight": 400, "locktime": 700,        # feerate 2 sat/vB
          "status": {"block_height": 900, "block_time": 9000},
          "_bc": {"prev_min": 50.0, "prev_time": 8000, "incl_time": 9000}}  # prev_min 50 >= 2 -> loose
    assert locktime_class(tx, 900) == "height_other"         # plain axis: misleading "backdated"
    assert x_locktime_vs_broadcast(tx) == "na_loose"         # broadcast axis: correctly abstains
    # tight case (included quickly): the two agree that locktime tracks broadcast
    tx["_bc"]["prev_min"] = 1.0                               # prev_min 1 < 2 -> tight, broadcast ~ 900
    tx["locktime"] = 899
    assert x_locktime_vs_broadcast(tx) == "matches"

from decluster.broadcast import tx_time, active_hours, schedule_distance

def test_cluster_temporal():
    # Alice's cluster active ~03:00 UTC, Bob's ~15:00 UTC -> disjoint schedules -> distinguishable
    alice = active_hours([10800, 10860, 10920])       # 03:00-03:02 UTC
    bob   = active_hours([54000, 54060])              # 15:00 UTC
    assert alice[3] == 3 and bob[15] == 2
    assert schedule_distance(alice, bob) == 1.0        # disjoint schedules
    assert schedule_distance(alice, alice) == 0.0      # same schedule
    # tx_time: tight bound -> window midpoint; else inclusion time
    tight = {"fee": 1000, "weight": 400, "status": {"block_time": 9000},
             "_bc": {"prev_min": 5.0, "prev_time": 8000, "incl_time": 9000}}
    assert tx_time(tight) == 8500                       # (8000+9000)/2
    assert tx_time({"status": {"block_time": 9000}}) == 9000   # no tight bound -> inclusion time

from decluster.broadcast import calibrate_temporal

def test_calibrate_temporal():
    # two owner groups with distinct, PERSISTENT schedules (03:00 vs 15:00 UTC): a genuine
    # signal survives even the band-width-matched control (positive control for the harness)
    h = 3600
    rows = ([{"addr": f"A{i}", "times": [3*h + j*60 for j in range(10)]} for i in range(10)] +
            [{"addr": f"B{i}", "times": [15*h + j*60 for j in range(10)]} for i in range(10)])
    n, base, per, matched = calibrate_temporal(rows)
    assert n == 20
    assert per > 0.5 and matched > 0.5    # persistent + distinct -> survives both controls

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"): fn(); print(f"  ok  {name}")
    print("done")
