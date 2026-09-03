"""Emit a machine-readable temporal FS evaluation; no narrative result is hand-written."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from decluster.fingerprint_validate import load_blkcache
from decluster.fs_temporal import evaluate_temporal
from decluster.reproducibility import fingerprint_source


def source_identity(source):
    if source.is_dir():
        return fingerprint_source(str(source / "*.json"))
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(source), "bytes": source.stat().st_size,
            "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", default=".blkcache",
                        help="JSON transaction list, or a .blkcache directory")
    parser.add_argument("--cap", type=int, default=4000)
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    source = Path(args.source)
    if source.is_dir():
        txs = load_blkcache(str(source))
    else:
        with source.open() as stream:
            txs = json.load(stream)
    result = evaluate_temporal(txs, train_fraction=args.train_fraction,
                               cap=args.cap, seed=args.seed)
    result["source"] = source_identity(source)
    result["source"]["transactions"] = len(txs)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
