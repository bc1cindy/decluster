"""Publish the CTP observer-knowledge matrix without inferring protocol or ownership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..failure_modes.collaborative_forms import (
    CollaborativeForm,
    Observer,
    form_matrix,
    knowledge,
)
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "collaborative-forms-v1"


class VerificationError(ValueError):
    """A stored result differs from the executable observer-knowledge matrix."""


def _observation(contract):
    return {
        "inputs_sat": list(contract.observation.inputs),
        "outputs_sat": list(contract.observation.outputs),
    }


def _row(contract):
    return {
        "form": contract.form.value,
        "participants": contract.participants,
        "observation": _observation(contract),
        "transport": contract.transport,
        "external_onchain_knowledge": list(knowledge(contract, Observer.EXTERNAL)),
        "counterparty_knowledge": list(knowledge(contract, Observer.COUNTERPARTY)),
        "limitations": list(contract.limitations),
    }


def build_artifact():
    contracts = form_matrix()
    two_party = (
        CollaborativeForm.ORDINARY_TWO_INPUT,
        CollaborativeForm.P2EP,
        CollaborativeForm.BIP79,
        CollaborativeForm.BIP78,
        CollaborativeForm.BIP77,
    )
    rows = [_row(contract) for contract in contracts]
    by_form = {row["form"]: row for row in rows}
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "claim": "observable transaction data do not by themselves identify the collaborative form, participant allocation, payment graph or ownership",
        "two_party_onchain_equivalence": {
            "forms": [form.value for form in two_party],
            "observation": by_form[two_party[0].value]["observation"],
            "distinct_transports": len({
                by_form[form.value]["transport"] for form in two_party
            }),
        },
        "forms": rows,
        "conclusion": "identical on-chain amounts remain compatible with an ordinary spend and several two-party PayJoin protocols; counterparty knowledge must not be assigned to an external observer",
        "limitations": [
            "the participant allocations and payment relationships are supplied model possibilities",
            "protocol deployment frequency and empirical indistinguishability are not measured",
            "transport differences are not treated as on-chain observations",
            "the matrix is not ownership attribution or a privacy score",
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
        raise VerificationError("unsupported collaborative-forms artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from the executable observer-knowledge matrix")
    return measured


def render_markdown(artifact):
    rows = artifact["forms"]
    equivalent = artifact["two_party_onchain_equivalence"]
    lines = [
        "# Collaborative transaction observer-knowledge matrix",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "The same two-input/two-output observation is compatible with an ordinary transaction and four PayJoin protocol forms. This does not identify which protocol form occurred.",
        "",
        "| form | participants | external on-chain facts | counterparty facts |",
        "|---|---:|---|---|",
    ]
    for row in rows:
        participants = "latent" if row["participants"] is None else row["participants"]
        external = "; ".join(row["external_onchain_knowledge"])
        counterparty = "; ".join(row["counterparty_knowledge"]) or "not applicable"
        lines.append(f"| {row['form']} | {participants} | {external} | {counterparty} |")
    lines.extend([
        "",
        f"The shared observation is inputs `{equivalent['observation']['inputs_sat']}` and outputs `{equivalent['observation']['outputs_sat']}`. Protocol transport, participant allocation and negotiated payments are not added to the external observer's on-chain knowledge.",
        "",
        "All allocations and relationships in this fixture are supplied possible worlds. The result is not ownership attribution, a deployment-frequency measurement or a privacy score.",
        "",
    ])
    return "\n".join(lines)


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
