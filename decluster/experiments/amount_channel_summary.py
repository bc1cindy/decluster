"""Compose the amount-channel report exclusively from canonical upstream artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "amount-channel-survey-v1"
COMPONENTS = {
    "local": (
        "results/artifacts/amount-local-channels-v1.json",
        "amount-local-channels-v1",
        "210ecb06ecaa32cc4cabe03ced8b85b0882a824dca2c361bd2c5dede7dcccf02",
    ),
    "subset_sum": (
        "results/artifacts/amount-subset-sum-v1.json",
        "amount-subset-sum-v1",
        "240592b5af814fbcd28b06221805b934424170119da5e62e9da0281944377a9d",
    ),
    "per_coin": (
        "results/artifacts/amount-per-coin-v1.json",
        "amount-per-coin-v1",
        "7be46858e221d0c942e7fa3ccc93b5eba28cf3a494fd00f07c2d50f2caa473df",
    ),
    "mapping_family": (
        "results/artifacts/amount-mapping-family-v1.json",
        "amount-mapping-family-v1",
        "11f0ec645ea1be334dc7d24fbfc31047b234f335f48b5a514960472c7444b7d6",
    ),
    "pairwise_family": (
        "results/artifacts/amount-pairwise-family-v1.json",
        "amount-pairwise-family-v1",
        "83f6a9e8501ee4df45f08b8c8ffc2f7265d40bf9add6d3f5093d712657c9dbf5",
    ),
}


class VerificationError(ValueError):
    """An input or generated result violates the composition contract."""


def _load_component(path, expected_experiment, expected_sha256):
    source = Path(path)
    try:
        payload = source.read_bytes()
        value = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read component {path}: {exc}") from exc
    digest = hashlib.sha256(payload).hexdigest()
    if digest != expected_sha256:
        raise VerificationError(
            f"component {path} has SHA-256 {digest}, expected {expected_sha256}"
        )
    if not isinstance(value, dict) or value.get("experiment") != expected_experiment:
        raise VerificationError(f"component {path} has the wrong experiment identity")
    return value


def build_report(paths=None):
    paths = paths or {name: spec[0] for name, spec in COMPONENTS.items()}
    components = {}
    identities = {}
    for name, (_default, experiment, digest) in COMPONENTS.items():
        path = paths[name]
        components[name] = _load_component(path, experiment, digest)
        identities[name] = {"experiment": experiment, "sha256": digest}

    local = components["local"]["report"]
    subset_sum = components["subset_sum"]["report"]
    per_coin = components["per_coin"]["report"]
    mapping = components["mapping_family"]["report"]
    pairwise = components["pairwise_family"]["report"]
    return {
        "components": identities,
        "population": local["population"],
        "local_channels": {
            "coinjoin": local["coinjoin"],
            "unnecessary_input": local["unnecessary_input"],
            "subtransaction_roundness": local["subtransaction_roundness"],
            "conservation": local["conservation"],
        },
        "transaction_subset_sum": subset_sum["outcomes"],
        "per_coin_density": per_coin["per_coin_density"],
        "per_coin_candidates": {
            "ungated": per_coin["ungated_diagnostic"],
            "transaction_gated": per_coin["transaction_gated"],
        },
        "mapping_family": {
            "outcomes": mapping["outcomes"],
            "restricted_family": mapping["restricted_family"],
        },
        "pairwise_family": {
            "outcomes": pairwise["outcomes"],
            "restricted_family_rows": pairwise["restricted_family_rows"],
        },
    }


def build_artifact(paths=None):
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "report": build_report(paths),
        "limitations": [
            "this artifact composes upstream results and performs no mechanism calculation",
            "component SHA-256 identities are mandatory",
            "the five components measure different objects and are not combined into one score",
            "DSS mapping and pairwise claims remain restricted to DSS's mapping family",
            "the Bitcoin snapshot covers one 137-block interval from 2023",
            "this summary is not a privacy certificate or CoinScore",
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


def verify_artifact(artifact, *, paths=None):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported amount-channel summary identity")
    measured = build_artifact(paths)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from the canonical component composition")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    population = report["population"]
    local = report["local_channels"]
    subset_sum = report["transaction_subset_sum"]
    per_coin = report["per_coin_candidates"]
    mapping = report["mapping_family"]
    pairwise = report["pairwise_family"]
    return "\n".join([
        "# Amount-channel survey",
        "",
        "Generated only from five SHA-256-pinned canonical artifacts. Do not edit manually.",
        "",
        f"The snapshot contains {population['transactions']:,} transactions and "
        f"{population['multi_input']:,} complete multi-input transactions.",
        "",
        "## Independent local channels",
        "",
        f"CoinJoin shape fires {local['coinjoin']['shape_detected']:,} times and de-mix resolves "
        f"{local['coinjoin']['demixed']:,}. Unnecessary-input fires "
        f"{local['unnecessary_input']['fires']:,} times. Roundness ranks "
        f"{local['subtransaction_roundness']['ranked']:,} 2×2 transactions, with "
        f"{local['subtransaction_roundness']['top_tied']:,} top ties. The conservation probe "
        f"forces an output value {local['conservation']['forced_output_value']:,} times under its "
        "declared largest-input assumption.",
        "",
        "## Subset-sum diagnostics",
        "",
        f"Transaction W(E) returns {subset_sum['by_kind'].get('exact', 0):,} exact and "
        f"{subset_sum['by_kind'].get('unknown', 0):,} unknown outcomes; "
        f"{subset_sum['guaranteed_nonzero_log_w']:,} expose a usable conservative nonzero log W.",
        "",
        f"Per-coin density yields {per_coin['ungated']['candidates']['total']:,} raw candidates. "
        f"After the transaction gate, {per_coin['transaction_gated']['candidates']['total']:,} "
        f"remain in {per_coin['transaction_gated']['candidate_transactions']:,} transactions.",
        "",
        "## Restricted DSS mapping family",
        "",
        f"Mapping analysis answers {mapping['outcomes']['answered']:,} of 250 transactions; "
        f"{mapping['restricted_family']['entropy_bins_bits']['zero']:,} answered families have "
        "zero-bit entropy. Pairwise analysis returns "
        f"{pairwise['restricted_family_rows']['returned']:,} rows, including "
        f"{pairwise['restricted_family_rows']['singleton_support']:,} singleton-support rows.",
        "",
        "Entropy, certainty and support in the final section apply only to DSS's restricted "
        "mapping family. The components remain separate and are not a privacy score.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, (default, _experiment, _digest) in COMPONENTS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", default=default)
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
    paths = {name: getattr(args, name) for name in COMPONENTS}
    if args.command == "reproduce":
        artifact = build_artifact(paths)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), paths=paths)
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
