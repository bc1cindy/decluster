"""Graph-level demo on the ancestry graph of the real merged transaction 931d6627.
Shows the COLLAPSE of single-heuristic union-find vs. fingerprint-aware clustering."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster import fetch_tx
from decluster.combiner import Combiner
from decluster.cluster import cluster_naive, cluster_fingerprint_aware
from decluster.extractors import x_nsequence


def main():
    # set of coins (txs that funded the coins) in the ancestry graph of the merged transaction
    full = {"931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4",
            "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729",
            "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"}
    full.add(fetch_tx("0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729")["vin"][0]["txid"]) # be2e
    for v in fetch_tx("91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a")["vin"]:
        full.add(v["txid"])  # 5b97,89300d,b8c2bd
    nodes = full

    def label(t): return f"{t[:10]}.. [{x_nsequence(fetch_tx(t)):14}]"

    print(f"graph: {len(nodes)} coins\n")
    print("=== 1) UNION-FIND single-heuristic (common-input-ownership, BlockSci style) ===")
    for g in cluster_naive(nodes):
        print(f"  cluster ({len(g)}): " + ", ".join(sorted(label(x) for x in g)))

    print("\nbuilding combiner (real measured bits, library.py / WP2)...")
    cmb = Combiner.from_library()

    print("\n=== 2) FINGERPRINT-AWARE CLUSTERING ===")
    groups, refused, linked = cluster_fingerprint_aware(nodes, cmb)
    for g in groups:
        print(f"  cluster ({len(g)}): " + ", ".join(sorted(label(x) for x in g)))
    print("\n  REFUSED merges (merged transaction re-partitioned):")
    for a, b, t, sc in refused:
        print(f"    {a[:10]}.. <-x-> {b[:10]}..  ({sc:+.1f} bits)  co-spent in {t[:10]}..")
    print("  ADDED links (rare fingerprint that co-spend missed):")
    for a, b, sc in linked:
        print(f"    {a[:10]}.. <--> {b[:10]}..  ({sc:+.1f} bits)")


if __name__ == "__main__":
    main()
