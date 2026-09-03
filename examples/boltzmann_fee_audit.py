"""Compare exact conservation, explicit fee allocation, and roundness on local transactions.

This is a measurement of decluster's local bounded enumerator, not parity with Boltzmann.
usage: python3 examples/boltzmann_fee_audit.py [sample.ndjson] [--cap 300] [--manifest]
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import reproducibility
from decluster.baselines.boltzmann import exact_link_analysis, fee_tolerant_link_analysis
from decluster.measure import load_ndjson
from decluster.subtransaction import roundness

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = "RESULTS-boltzmann-fee-audit.md"


def values(tx):
    vin = tx.get("vin") or []
    vout = tx.get("vout") or []
    inputs = [(item.get("prevout") or {}).get("value") for item in vin]
    outputs = [item.get("value") for item in vout]
    if len(inputs) < 2 or not outputs or any(value is None for value in inputs + outputs):
        return None
    return tuple(inputs), tuple(outputs)


def audit(path, cap=300, max_coins=8):
    selected = []
    for tx, _height in load_ndjson(path):
        pair = values(tx)
        if pair is None or sum(map(len, pair)) > max_coins:
            continue
        selected.append((tx.get("txid"), *pair))
        if len(selected) == cap:
            break

    rows = []
    for txid, inputs, outputs in selected:
        fee = sum(inputs) - sum(outputs)
        exact = exact_link_analysis(inputs, outputs, max_coins=max_coins)
        tolerant = (fee_tolerant_link_analysis(inputs, outputs, fee_tolerance=fee,
                                               max_coins=max_coins)
                    if fee >= 0 else None)
        rows.append({
            "txid": txid,
            "inputs": len(inputs), "outputs": len(outputs), "fee": fee,
            "fee_roundness": roundness(fee),
            "exact_mappings": len(exact.mappings),
            "fee_tolerant_mappings": len(tolerant.mappings) if tolerant is not None else None,
        })

    fees = [row["fee"] for row in rows]
    return {
        "configuration": {"cap": cap, "max_coins": max_coins},
        "population": {
            "selected": len(rows),
            "nonnegative_fee": sum(fee >= 0 for fee in fees),
            "positive_fee": sum(fee > 0 for fee in fees),
            "round_fee": sum(row["fee_roundness"] > 0 for row in rows),
        },
        "outcomes": {
            "exact_with_mapping": sum(row["exact_mappings"] > 0 for row in rows),
            "fee_tolerant_with_mapping": sum((row["fee_tolerant_mappings"] or 0) > 0
                                             for row in rows),
            "fee_tolerant_with_nontrivial_split": sum(
                (row["fee_tolerant_mappings"] or 0) > 1 for row in rows
            ),
            "max_fee_tolerant_mappings": max(
                (row["fee_tolerant_mappings"] or 0 for row in rows), default=0
            ),
            "round_fee_and_nontrivial_split": sum(
                row["fee_roundness"] > 0 and (row["fee_tolerant_mappings"] or 0) > 1
                for row in rows
            ),
            "mapping_count_relation": dict(sorted(Counter(
                "unavailable" if row["fee_tolerant_mappings"] is None else
                "equal" if row["exact_mappings"] == row["fee_tolerant_mappings"] else
                "fee_tolerant_more" if row["fee_tolerant_mappings"] > row["exact_mappings"] else
                "exact_more"
                for row in rows
            ).items())),
        },
        "rows": rows,
    }


def invariants(report):
    return {**report["configuration"], **report["population"], **report["outcomes"]}


def parser():
    out = argparse.ArgumentParser()
    out.add_argument("path", nargs="?", default="sample.ndjson")
    out.add_argument("--cap", type=int, default=300)
    out.add_argument("--max-coins", type=int, default=8)
    out.add_argument("--out", default="results/boltzmann-fee-audit.json")
    out.add_argument("--manifest", action="store_true")
    return out


def main(argv=None):
    args = parser().parse_args(argv)
    report = audit(os.path.join(ROOT, args.path), args.cap, args.max_coins)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out:
        with open(os.path.join(ROOT, args.out), "w") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
    if args.manifest:
        reproducibility.write_manifest(DOC, args.path, invariants(report), root=ROOT)


if __name__ == "__main__":
    main()
