"""Graph anonymity metric on a larger real ancestry graph of merged transaction
931d6627. Not chain scale — a real graph of tens of coins, not the base demo's 7."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.fetch import fetch_tx
from decluster.combiner import Combiner
from decluster.graph_metric import privacy_report

MERGE = "931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4"
CAP = 60

def ancestry(seed, depth):
    seen = set(seed)
    frontier = set(seed)
    for _ in range(depth):
        nxt = set()
        for t in frontier:
            if len(seen) >= CAP: break
            try:
                for v in fetch_tx(t)["vin"]:
                    if v.get("is_coinbase"): continue
                    p = v["txid"]
                    if p not in seen and len(seen) < CAP:
                        seen.add(p); nxt.add(p)
            except Exception:
                continue
        frontier = nxt
    return seen

if __name__ == "__main__":
    nodes = ancestry({MERGE}, depth=6)
    print(f"ancestry graph (depth-6, cap {CAP}): {len(nodes)} coins")
    rep = privacy_report(nodes, Combiner.from_library())
    for label in ("union_find", "fingerprint_aware"):
        m = rep[label]
        print(f"  {label:18} clusters={m['clusters']:>3}  entropy={m['entropy_bits']:.2f} bits  "
              f"anon_set={m['eff_anon_set']:.1f}  largest_cluster={m['largest_frac']*100:.0f}%")
