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

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"): fn(); print(f"  ok  {name}")
    print("done")
