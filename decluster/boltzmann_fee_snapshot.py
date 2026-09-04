"""Build the exact transaction population used by the fee-allocation audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from .measure import load_ndjson
from .result_artifacts import write_canonical_json


def transaction_values(transaction):
    inputs = [
        (item.get("prevout") or {}).get("value")
        for item in (transaction.get("vin") or [])
    ]
    outputs = [item.get("value") for item in (transaction.get("vout") or [])]
    if (
        len(inputs) < 2
        or not outputs
        or any(value is None for value in inputs + outputs)
    ):
        return None
    return tuple(inputs), tuple(outputs)


def build_snapshot(source, destination, *, cap=300, max_coins=8):
    """Write the first ``cap`` eligible transactions in source order."""
    if cap < 1:
        raise ValueError("cap must be positive")
    if max_coins < 3:
        raise ValueError("max_coins must allow two inputs and one output")
    selected = []
    for transaction, _height in load_ndjson(source):
        values = transaction_values(transaction)
        if values is None or sum(map(len, values)) > max_coins:
            continue
        selected.append(transaction)
        if len(selected) == cap:
            break
    if len(selected) != cap:
        raise ValueError(f"source contains only {len(selected)} eligible transactions")
    write_canonical_json(Path(destination), selected)
    return len(selected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--cap", type=int, default=300)
    parser.add_argument("--max-coins", type=int, default=8)
    args = parser.parse_args(argv)
    build_snapshot(args.source, args.destination, cap=args.cap, max_coins=args.max_coins)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
