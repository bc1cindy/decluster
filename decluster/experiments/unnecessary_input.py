"""Reproduce the fee-aware unnecessary-input diagnostic and its limits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..baselines.unnecessary_input import (
    UIHStatus,
    analyze_blockstream,
    blocksci_uih1,
    gibson_flags,
)
from ..failure_modes.unnecessary_input import (
    collaborative_form_examples,
    cycle_equivalent_obligations,
    evaluate,
    net_balances,
    observationally_equivalent_example,
)
from ..result_artifacts import canonical_json_bytes, write_canonical_json


EXPERIMENT_ID = "unnecessary-input-v2"
DEFINITION = "blockstream_fee_aware"
DEFINITION_VERSION = 2


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def _classification(inputs: tuple[int, ...], outputs: tuple[int, ...]) -> dict:
    analysis = analyze_blockstream(inputs, outputs)
    return {
        "inputs": list(inputs),
        "outputs": list(outputs),
        "status": analysis.status.value,
        "fee": analysis.fee,
        "removed_input_index": analysis.removed_input_index,
        "change_output_index": analysis.change_output_index,
        "reason": analysis.reason,
        "blocksci_strict_uih1": blocksci_uih1(inputs, outputs),
        "gibson_flags": list(flags) if (flags := gibson_flags(inputs, outputs)) else None,
    }


def build_artifact() -> dict:
    equivalent = observationally_equivalent_example()
    report = evaluate(equivalent)
    evidence = report.channels[0].evidence[0]
    ns1r, nsnr = collaborative_form_examples()
    simple, with_cycle = cycle_equivalent_obligations()
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "diagnostic": {
            "definition": DEFINITION,
            "semantic_version": DEFINITION_VERSION,
            "paper_domain": {
                "minimum_inputs": 2,
                "exact_outputs": 2,
                "amounts": "positive unsigned 64-bit integers",
            },
        },
        "boundary_cases": {
            "jointly_funded_uih2": _classification((6, 6, 6), (10, 7)),
            "fee_aware_uih1": _classification((10, 2), (10, 1)),
            "equality_boundary": _classification((10, 2), (9, 2)),
        },
        "observational_equivalence": {
            "classification": evidence.classification,
            "fee": evidence.fee,
            "possible_forms": [form.value for form in equivalent.possible_forms],
            "decision": type(report.outcomes[0]).__name__.lower(),
            "ownership_inferred": False,
            "payjoin_identified": False,
            "payment_output_identified": False,
            "composition": report.composition,
        },
        "scope_controls": {
            ns1r.form.value: _classification(ns1r.inputs, ns1r.outputs),
            nsnr.form.value: _classification(nsnr.inputs, nsnr.outputs),
        },
        "cycle_control": {
            "simple_nonzero_net_balances": {
                party: balance for party, balance in net_balances(simple).items() if balance
            },
            "cyclic_nonzero_net_balances": {
                party: balance for party, balance in net_balances(with_cycle).items() if balance
            },
            "simple_gross_amount": sum(item.amount for item in simple),
            "cyclic_gross_amount": sum(item.amount for item in with_cycle),
        },
        "conclusion": (
            "the fee-aware predicate classifies a two-output amount shape; it does not "
            "identify PayJoin, ownership, participant roles, or gross obligations"
        ),
        "limitations": list(report.limitations),
    }


def load_artifact(path: str | Path) -> dict:
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("artifact root must be an object")
    return value


def verify_artifact(artifact: dict) -> dict:
    identity = (artifact.get("schema_version"), artifact.get("experiment"))
    if identity != (1, EXPERIMENT_ID):
        raise VerificationError("unsupported unnecessary-input artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh diagnostic execution")
    return measured


def render_markdown(artifact: dict) -> str:
    cases = artifact["boundary_cases"]
    equivalence = artifact["observational_equivalence"]
    scopes = artifact["scope_controls"]
    cycle = artifact["cycle_control"]
    rows = [
        (name.replace("_", " "), case["status"], case["fee"], case["gibson_flags"])
        for name, case in cases.items()
    ]
    lines = [
        "# Fee-aware unnecessary-input diagnostic",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "Definition: "
        f"`{artifact['diagnostic']['definition']}` "
        f"v{artifact['diagnostic']['semantic_version']}.",
        "Its paper domain is transactions with at least two inputs and exactly two outputs.",
        "",
        "| case | classification | fee | Gibson flags |",
        "|---|---|---:|---|",
    ]
    lines.extend(
        f"| {name} | {status} | {fee} | `{flags}` |" for name, status, fee, flags in rows
    )
    lines.extend([
        "",
        "The observational-equivalence fixture is classified "
        f"`{equivalence['classification']}`, yet remains `{equivalence['decision']}` across "
        f"{len(equivalence['possible_forms'])} declared latent forms. It infers no ownership, "
        "PayJoin identity, payment output, or composition.",
        "",
        "NS1R and NSNR controls are outside the two-output definition: "
        f"`{scopes['many_senders_one_receiver']['status']}` and "
        f"`{scopes['many_senders_many_receivers']['status']}`.",
        "",
        "The cycle control preserves the nonzero net balances while changing gross obligations "
        f"from {cycle['simple_gross_amount']} to {cycle['cyclic_gross_amount']}. Therefore the "
        "gross payment graph is not identified by the on-chain net amounts.",
        "",
        "This is a deterministic diagnostic reproduction, not a PayJoin detector, ownership "
        "classifier, prevalence estimate, or privacy score.",
        "",
    ])
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    reproduce = commands.add_parser("reproduce")
    reproduce.add_argument("--artifact", required=True)
    reproduce.add_argument("--markdown", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True)
    verify.add_argument("--markdown")
    return parser


def main(argv: list[str] | None = None) -> int:
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
            try:
                actual = Path(args.markdown).read_text(encoding="utf-8")
            except OSError as exc:
                raise VerificationError(f"cannot read Markdown {args.markdown}: {exc}") from exc
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
