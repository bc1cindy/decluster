"""Demo grafo-level no grafo de ancestralidade do merged transaction real 931d6627.
Mostra o COLAPSO do union-find single-heuristic vs. o clustering ciente de fingerprint."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster import fetch_tx
from decluster.combiner import Combiner
from decluster.cluster import cluster_naive, cluster_fingerprint_aware
from decluster.extractors import x_nsequence


def main():
    # conjunto de coins (txs que fundaram os coins) no grafo de ancestralidade do merged transaction
    full = {"931d6627f7b63491cbc2e6d860dc630537385fd9ee3171f2013b64e6a143a4e4",
            "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729",
            "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"}
    full.add(fetch_tx("0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729")["vin"][0]["txid"]) # be2e
    for v in fetch_tx("91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a")["vin"]:
        full.add(v["txid"])  # 5b97,89300d,b8c2bd
    nodes = full

    def label(t): return f"{t[:10]}.. [{x_nsequence(fetch_tx(t)):14}]"

    print(f"grafo: {len(nodes)} coins\n")
    print("=== 1) UNION-FIND single-heuristic (common-input-ownership, estilo BlockSci) ===")
    for g in cluster_naive(nodes):
        print(f"  cluster ({len(g)}): " + ", ".join(sorted(label(x) for x in g)))

    print("\nconstruindo combinador (bits reais medidos, library.py / WP2)...")
    cmb = Combiner.from_library()

    print("\n=== 2) CLUSTERING ciente de fingerprint ===")
    groups, refused, linked = cluster_fingerprint_aware(nodes, cmb)
    for g in groups:
        print(f"  cluster ({len(g)}): " + ", ".join(sorted(label(x) for x in g)))
    print("\n  merges RECUSADOS (merged transaction re-particionado):")
    for a, b, t, sc in refused:
        print(f"    {a[:10]}.. <-x-> {b[:10]}..  ({sc:+.1f} bits)  co-gastos em {t[:10]}..")
    print("  links ADICIONADOS (fingerprint raro que o co-spend perdeu):")
    for a, b, sc in linked:
        print(f"    {a[:10]}.. <--> {b[:10]}..  ({sc:+.1f} bits)")


if __name__ == "__main__":
    main()
