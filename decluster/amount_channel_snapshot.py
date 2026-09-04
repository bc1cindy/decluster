"""Build the canonical transaction snapshot used by amount-channel experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from .measure import load_ndjson
from .result_artifacts import write_canonical_json


def build_snapshot(source, destination, *, expected_records=None):
    """Normalize all source transactions while preserving their observed order."""
    transactions = [transaction for transaction, _height in load_ndjson(source)]
    if expected_records is not None and len(transactions) != expected_records:
        raise ValueError(
            f"expected {expected_records} transactions, found {len(transactions)}"
        )
    write_canonical_json(Path(destination), transactions)
    return len(transactions)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--expected-records", type=int)
    args = parser.parse_args(argv)
    build_snapshot(
        args.source,
        args.destination,
        expected_records=args.expected_records,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
