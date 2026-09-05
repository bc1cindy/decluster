"""Run the independently reconstructed nominal CoinJoin Sudoku mechanism."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baselines.coinjoin_sudoku import (
    collapse_fee_permutations,
    equal_sum_groupings,
    maximally_separated_groupings,
    uniform_link_probabilities,
)
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "coinjoin-sudoku-nominal-v1"
SOURCE_REVISION = "afbd2658b4ac9e0711b12c1bd4ab228ea5dd2499"


class VerificationError(ValueError):
    """A stored result differs from a fresh nominal reconstruction."""


def build_artifact():
    sx_inputs = (1_010_000,) * 3
    sx_outputs = (1_000_000,) * 3
    sx_all = equal_sum_groupings(sx_inputs, sx_outputs, fee_unit=10_000)
    sx_selected = maximally_separated_groupings(
        sx_inputs, sx_outputs, fee_unit=10_000
    )
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "source": {
            "advisory": "https://www.coinjoinsudoku.com/advisory/",
            "repository_revision": SOURCE_REVISION,
            "historical_analyzer_available": False,
        },
        "published_mechanism": {
            "balance": "exact integer sum per paired group",
            "selection": "all valid equal-sum groupings",
            "fee_constraint": "fee is a multiple of a constant, currently 0.0001 BTC",
        },
        "local_adaptation": {
            "selection": "valid interpretations with the largest group count",
            "weighting": "uniform over indexed selected groupings",
            "fee_model": "the fee split into explicit equal pseudo-outputs of one fee unit",
            "purpose": "reconstruct the SX symmetry argument under explicit semantics",
        },
        "advisory_group_examples": {
            "valid_2_plus_3_to_1_plus_4": len(equal_sum_groupings((2, 3), (1, 4))),
            "invalid_2_plus_3_to_1_plus_2": len(equal_sum_groupings((2, 3), (1, 2))),
        },
        "sx_symmetric_control": {
            "txid": "9256332b9ca52cbcb06f57296dfd982d8da3f7d4696b4c10cf9bb93dae6edf58",
            "inputs_sat": list(sx_inputs),
            "outputs_sat": list(sx_outputs),
            "fee_sat": 30_000,
            "fee_unit_sat": 10_000,
            "all_equal_sum_groupings": len(sx_all),
            "selected_indexed_groupings": len(sx_selected),
            "selected_groupings_collapsing_fee_permutations": len(
                collapse_fee_permutations(sx_selected, len(sx_outputs))
            ),
            "local_uniform_real_output_link_probabilities": uniform_link_probabilities(
                sx_inputs, sx_outputs, fee_unit=10_000
            ),
        },
        "sharedcoin_historical_target": {
            "txid": "0e0337bdf930eba3b082fdfbd30944b18e03f0f810ae531443161f897a4d3db0",
            "reported_grouped_inputs_percent": 69,
            "reported_grouped_outputs_percent": 53,
            "status": "not_reproduced",
            "reason": "the analyzer and complete output-label semantics were not published",
        },
        "composition": None,
        "conclusion": "the published mechanism accepts the advisory's balanced example; a separately labelled maximal/uniform adaptation recovers the SX control's one-third symmetry",
        "limitations": [
            "this is an independent reconstruction, not parity with the unavailable historical analyzer",
            "largest-group selection, uniform weighting and the fee pseudo-output split are local semantics, not published analyzer rules",
            "the marginals are a function of the local fee unit: at one 30,000-sat unit the same control reads 1.0 instead of one third",
            "digit skipping and the reported 2014 SharedCoin grouping result are not reproduced",
            "amount relations within this family are not ownership attribution",
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
        raise VerificationError("unsupported CoinJoin Sudoku artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh nominal reconstruction")
    return measured


def render_markdown(artifact):
    sx = artifact["sx_symmetric_control"]
    probability = sx["local_uniform_real_output_link_probabilities"][0][0]
    target = artifact["sharedcoin_historical_target"]
    return "\n".join([
        "# CoinJoin Sudoku nominal reconstruction",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "The independently implemented nominal mechanism retains exact equal-sum input/output groupings. The cited repository does not contain the historical analyzer, so this result does not claim code parity.",
        "",
        "| primary-source fixture | retained mappings | representative input/output relation |",
        "|---|---:|---:|",
        f"| SX symmetric control | {sx['selected_indexed_groupings']} indexed / {sx['selected_groupings_collapsing_fee_permutations']} fee-collapsed | {probability:.6f} |",
        "",
        f"The advisory's larger SharedCoin target `{target['txid']}` remains **not reproduced**: its analyzer and complete output-label semantics were not published.",
        "",
        "The source-backed layer enumerates all exact equal-sum groupings. The displayed marginal comes from a separate local adaptation: explicit 10,000-sat fee pseudo-outputs, largest-group selection, and uniform weighting. Those rules are not attributed to the unavailable analyzer, and the resulting conditional amount relations are not ownership attribution.",
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
        if args.markdown is not None and Path(args.markdown).read_text(
            encoding="utf-8"
        ) != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
