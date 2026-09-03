"""Emit a machine-readable FS ablation study; no narrative result is hand-written."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decluster.fingerprint_validate import load_blkcache
from decluster.fs_ablation import run_ablation_study
from decluster.reproducibility import fingerprint_source


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default=".blkcache",
                        help="JSON transaction list, or a .blkcache directory")
    parser.add_argument("--ablation-cap", type=int, default=4000)
    parser.add_argument("--association-cap", type=int, default=8000)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cluster-threshold", type=float, default=0.6)
    args = parser.parse_args()
    source = Path(args.source)
    if source.is_dir():
        txs = load_blkcache(str(source))
        source_identity = fingerprint_source(str(source / "*.json"))
    else:
        with source.open() as stream:
            txs = json.load(stream)
        source_identity = {"path": str(source)}
    result = run_ablation_study(
        txs, train_fraction=args.train_fraction, ablation_cap=args.ablation_cap,
        association_cap=args.association_cap, seed=args.seed,
        cluster_threshold=args.cluster_threshold,
    )
    result["source"] = source_identity
    result["source"]["transactions"] = len(txs)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
