"""Exercise the public analysis facade on a deterministic transaction graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..analyze import analyze
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "analyze-contract-v1"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


TRANSACTIONS = {
    "target": {
        "txid": "target",
        "vin": [
            {"txid": "left", "vout": 0,
             "prevout": {"value": 500, "scriptpubkey_address": "owner-left"}},
            {"txid": "right", "vout": 0, "prevout": {"value": 500}},
        ],
        "vout": [
            {"value": 600, "scriptpubkey_address": "external"},
            {"value": 399, "scriptpubkey_address": "owner-left"},
        ],
    },
    "left": {
        "txid": "left",
        "vin": [{
            "txid": "origin-left",
            "vout": 0,
            "prevout": {"value": 500, "scriptpubkey_address": "owner-left"},
        }],
        "vout": [{"value": 500}],
    },
    "right": {
        "txid": "right",
        "vin": [{"txid": "origin-right", "vout": 0, "prevout": {"value": 500}}],
        "vout": [{"value": 500}],
    },
    "origin-left": {
        "txid": "origin-left",
        "vin": [{"is_coinbase": True}],
        "vout": [{"value": 500}],
    },
    "origin-right": {
        "txid": "origin-right",
        "vin": [{"is_coinbase": True}],
        "vout": [{"value": 500}],
    },
}


def _fetch(txid):
    return TRANSACTIONS[txid]


def _number(value):
    return round(value, 15)


def _summary(entry):
    provenance = entry["provenance"]
    return {
        "provenance": {
            "min_entropy_bits": _number(provenance["min_entropy"]),
            "shannon_bits": _number(provenance["shannon"]),
            "n_absorbers": provenance["n_absorbers"],
        },
        "fused": {
            "min_entropy_bits": _number(entry["fused"]["min_entropy"]),
            "shannon_bits": _number(entry["fused"]["shannon"]),
        },
        "truncated": entry["truncated"],
    }


def build_artifact():
    depth_sweep = {}
    for depth in range(1, 6):
        result = analyze("target", targets=[0], depth=depth, fetch=_fetch)
        depth_sweep[str(depth)] = _summary(result[0])

    change = analyze("target", targets=[1], depth=1, fetch=_fetch)[1]
    uncapped = analyze("target", targets=[0], depth=5, fetch=_fetch)[0]
    capped = analyze("target", targets=[0], depth=5, fetch=_fetch, max_nodes=1)[0]
    route = analyze(
        "target", targets=[0], depth=2, fetch=_fetch, subjective=False, path_count=True,
    )[0]

    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "fixture": {"transactions": len(TRANSACTIONS), "targets": [0, 1]},
        "depth_sweep": depth_sweep,
        "change_fusion": {
            "provenance_min_entropy_bits": _number(change["provenance"]["min_entropy"]),
            "fused_min_entropy_bits": _number(change["fused"]["min_entropy"]),
            "sharpened": change["fused"]["min_entropy"] < change["provenance"]["min_entropy"],
        },
        "node_cap": {
            "uncapped_truncations": uncapped["truncated"],
            "capped_truncations": capped["truncated"],
            "cap_is_observable": capped["truncated"] > uncapped["truncated"],
        },
        "route_diagnostic": {
            "present_when_requested": "path_count" in route,
            "canonical_meaning": "provenance_route_accumulation",
        },
        "capabilities": {
            "offline_transaction_input": True,
            "deterministic_value_flow_default": True,
            "depths_one_through_five_return": True,
            "subjective_fusion_never_widens": True,
            "truncation_is_reported": True,
        },
        "limitations": [
            "the fixture is synthetic and validates the public facade contract",
            "the run does not reproduce the historical live Bitcoin measurements",
            "address reuse is a heuristic subjective signal, not verified ownership",
            "provenance entropy is not a privacy certificate or CoinScore",
            "the path_count response key is retained for API compatibility only",
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
        raise VerificationError("unsupported analyze-contract artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh contract execution")
    return measured


def render_markdown(artifact):
    change = artifact["change_fusion"]
    cap = artifact["node_cap"]
    return "\n".join([
        "# Public analysis facade contract",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "The deterministic fixture returns at depths 1 through 5 with the default nominal-value "
        "flow oracle.",
        "",
        f"The change target's min-entropy changes from "
        f"{change['provenance_min_entropy_bits']:.6f} to "
        f"{change['fused_min_entropy_bits']:.6f} bits after the address-reuse signal. "
        f"Sharpening was observed: `{change['sharpened']}`.",
        "",
        f"The uncapped walk reports {cap['uncapped_truncations']} truncations and the one-node cap "
        f"reports {cap['capped_truncations']}. The cap is observable: `{cap['cap_is_observable']}`.",
        "",
        "The opt-in `path_count` response field is a compatibility name for "
        "`provenance_route_accumulation`; it is not robust connectivity or k-routes.",
        "",
        "This run validates an API contract on a synthetic graph. It does not reproduce the "
        "historical live Bitcoin measurements and does not certify privacy.",
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
