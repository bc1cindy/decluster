"""Run the production approximations against the exact oracle and print the disagreement report.

The full family is every balanced zero-fee `(inputs, outputs)` over the values 1..4 with at least
two coins a side and at most eight coins in total, each sorted value multiset appearing once. Each
`dss` entry point is identified before it is compared, and the entry points that count a different
object (`w_count`, `radix_mappings`, `per_coin_density`, `subtransaction.subtransactions`) are
reported as
identifications, never scored as under- or overcounts. See `decluster/baselines/oracle_audit.py`.

Exits non-zero when the report carries a flag, so an approximation that starts exceeding the oracle
fails a pipeline rather than printing quietly.

usage: python3 examples/exact_oracle_audit.py [max_coins] [--cases] [--manifest]
       python3 examples/exact_oracle_audit.py | python3 -m json.tool
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import reproducibility
from decluster.baselines import oracle_audit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv):
    include_cases = "--cases" in argv
    sizes = [a for a in argv[1:] if not a.startswith("--")]
    max_coins = int(sizes[0]) if sizes else oracle_audit.FAMILY_MAX_COINS
    family = oracle_audit.enumerate_family(max_coins=max_coins)
    report = oracle_audit.audit(family, include_cases=include_cases)
    if "--manifest" in argv:
        # Only the full family backs the published document; a reduced run must not overwrite it.
        if max_coins != oracle_audit.FAMILY_MAX_COINS:
            sys.stderr.write("refusing to record a manifest for a reduced family\n")
            return 2
        reproducibility.write_manifest(
            oracle_audit.MANIFEST_DOC, oracle_audit.MANIFEST_SOURCE,
            oracle_audit.manifest_invariants(report), root=ROOT)
        path = reproducibility.manifest_path(oracle_audit.MANIFEST_DOC, ROOT)
        sys.stderr.write(f"wrote {path}\n")
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 1 if report["flags"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
