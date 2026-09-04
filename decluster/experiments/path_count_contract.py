"""Measure the implemented route-accumulation contract of path_count_anonymity."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ..ancestry import absorber_distribution, build_extended_graph
from ..path_count import path_count_anonymity
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "path-count-contract-v1"
TARGET = ("target", 0)


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _coinbase(value):
    return {"vin": [{"is_coinbase": True}], "vout": [{"value": value}]}


TRANSACTIONS = {
    "target": {
        "vin": [
            {"txid": "middle", "vout": 0, "prevout": {"value": 3}},
            {"txid": "middle", "vout": 1, "prevout": {"value": 4}},
        ],
        "vout": [{"value": 7}],
    },
    "middle": {
        "vin": [
            {"txid": "origin-a", "vout": 0, "prevout": {"value": 2}},
            {"txid": "origin-b", "vout": 0, "prevout": {"value": 5}},
        ],
        "vout": [{"value": 2}, {"value": 5}],
    },
    "origin-a": _coinbase(2),
    "origin-b": _coinbase(5),
}


def _fetch(txid):
    return TRANSACTIONS[txid]


def _link_oracle(inputs, outputs):
    if inputs == [3, 4]:
        return [[0.6], [0.4]]
    if inputs == [2, 5]:
        return [[0.7, 0.5], [0.3, 0.5]]
    return None


def _count_oracle(log_w):
    def count(_inputs, _outputs):
        return {"kind": "exact", "count": round(math.exp(log_w)), "log_w": log_w}

    return count


def _serialize_distribution(distribution):
    return {
        f"{txid}:{index}": round(probability, 15)
        for (txid, index), probability in sorted(distribution.items())
    }


def build_artifact():
    graph = build_extended_graph(TARGET, depth=6, fetch=_fetch, link_oracle=_link_oracle)
    ancestry = absorber_distribution(graph, TARGET)
    low_count = path_count_anonymity(
        TARGET,
        depth=6,
        fetch=_fetch,
        link_oracle=_link_oracle,
        count_oracle=_count_oracle(0.0),
    )
    high_count = path_count_anonymity(
        TARGET,
        depth=6,
        fetch=_fetch,
        link_oracle=_link_oracle,
        count_oracle=_count_oracle(math.log(100.0)),
    )
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "fixture": {"transactions": 4, "target": "target:0", "depth": 6},
        "ancestry_distribution": _serialize_distribution(ancestry),
        "path_count_distribution": _serialize_distribution(low_count["origins_weighted"]),
        "entropy": {
            "min_bits": low_count["min_entropy"],
            "shannon_bits": low_count["shannon"],
        },
        "count_oracle_invariance": {
            "low_log_w": 0.0,
            "high_log_w": math.log(100.0),
            "distributions_equal": (
                low_count["origins_weighted"] == high_count["origins_weighted"]
            ),
        },
        "implemented_capabilities": {
            "provenance_route_accumulation": True,
            "edge_disjoint_path_enumeration": False,
            "plausible_flow_capacity": False,
            "k_routes": False,
        },
        "limitations": [
            "the fixture is synthetic and tests implementation semantics",
            "the function accumulates link-probability mass over ancestry routes",
            "count_oracle is retained for compatibility and does not affect the result",
            "the function does not measure CTP robust connectivity or own-origin robustness",
            "the output is not a privacy score or CoinScore",
        ],
    }


def load_artifact(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("artifact root must be an object")
    return value


def verify_artifact(artifact):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported path-count-contract artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh contract execution")
    return measured


def render_markdown(artifact):
    capabilities = artifact["implemented_capabilities"]
    entropy = artifact["entropy"]
    return "\n".join([
        "# Path-count implementation contract",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "The ancestry and path-count distributions are identical on the fixed two-hop DAG: "
        f"`{artifact['path_count_distribution']}`.",
        "",
        f"The resulting min-entropy is {entropy['min_bits']:.6f} bits and Shannon entropy is "
        f"{entropy['shannon_bits']:.6f} bits. Changing the supplied count oracle from log W = 0 "
        f"to log W = ln(100) leaves the distribution unchanged: "
        f"`{artifact['count_oracle_invariance']['distributions_equal']}`.",
        "",
        f"Route accumulation is implemented: `{capabilities['provenance_route_accumulation']}`. "
        "Edge-disjoint path enumeration, plausible-flow capacity and k-routes are implemented: "
        f"`{capabilities['edge_disjoint_path_enumeration']}`, "
        f"`{capabilities['plausible_flow_capacity']}`, `{capabilities['k_routes']}`.",
        "",
        "This is a provenance-route diagnostic, not CTP robust connectivity or CoinScore.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact()
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact))
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
