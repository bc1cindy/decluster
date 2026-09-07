"""Publish the receiver-side change read-off in a many-senders/one-receiver PayJoin.

The receiver knows its own coins and the payment it negotiated with each sender, so every candidate
(input, change) pair has to satisfy `input - payment == change`. Read one sender at a time the
constraint usually leaves several candidates; enumerating the perfect matchings propagates it
across senders and can leave a single reading of the amounts.

The distinction the artifact keeps is between matchings and readings. Two matchings that assign
different output *indices* but the same output *amounts* are one reading, and a reading is what the
receiver actually learns. Reporting matchings alone would understate the leak.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..failure_modes.ns1r_change_readoff import analyze, ns1r_examples
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "ns1r-change-readoff-v1"


class VerificationError(ValueError):
    """A stored result differs from the executable read-off."""


def _scenario(readoff):
    scenario = readoff.scenario
    return {
        "identifier": scenario.identifier,
        "inputs_sat": list(scenario.inputs),
        "outputs_sat": list(scenario.outputs),
        "payments_sat": [{"sender": name, "payment": amount} for name, amount in scenario.payments],
        "local_candidates": {name: sorted(values) for name, values in readoff.local_candidates},
        "feasible_candidates": {name: sorted(values) for name, values in readoff.feasible_candidates},
        "matchings": len(readoff.matchings),
        "distinct_readings": len(readoff.readings),
        "reading_is_unique": len(readoff.readings) == 1,
        "unanimous_links": [list(link) for link in readoff.unanimous_links],
        "readings": [
            [{"sender": name, "input_sat": source, "change_sat": target}
             for name, source, target in reading]
            for reading in readoff.readings
        ],
    }


def build_artifact():
    rows = [_scenario(analyze(scenario)) for scenario in ns1r_examples()]
    resolved = [row for row in rows if row["reading_is_unique"]]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "claim": "a receiver who knows each negotiated payment can propagate the change constraint "
                 "across senders, and the propagation can leave one reading of the amounts where "
                 "no single sender's constraint does",
        "scenarios": rows,
        "measurement": {
            "scenarios": len(rows),
            "with_a_unique_reading": len(resolved),
            "locally_ambiguous_senders": sum(
                1 for row in rows for values in row["local_candidates"].values() if len(values) > 1
            ),
            "senders_narrowed_by_propagation": sum(
                1
                for row in rows
                for sender, local in row["local_candidates"].items()
                if len(row["feasible_candidates"][sender]) < len(local)
            ),
        },
        "conclusion": "propagation resolved the consolidating receiver to a single reading and left "
                      "the evenly spaced control with two; the read-off is a receiver capability, "
                      "not an external-observer one",
        "limitations": [
            "the scenarios are deterministic fixtures, not sampled transactions",
            "the receiver's knowledge of each negotiated payment is supplied, not inferred",
            "an external observer holds neither the payments nor the receiver's own coins",
            "a unique reading of the amounts is not ownership attribution",
            "the enumeration is bounded at eight senders and does not model fees",
            "the result is not a privacy score",
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
        raise VerificationError("unsupported change-read-off artifact identity")
    measured = build_artifact()
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from the executable read-off")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    lines = [
        "# Receiver-side change read-off in a many-senders PayJoin",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        "The receiver knows its own coins and the payment negotiated with each sender, so a "
        "candidate change output must satisfy `input - payment == change`. One sender's constraint "
        "rarely settles it; the perfect matchings propagate it across senders.",
        "",
        "| scenario | senders | matchings | distinct readings | unique reading | unanimous links |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for row in artifact["scenarios"]:
        lines.append(
            f"| {row['identifier']} | {len(row['payments_sat'])} | {row['matchings']} | "
            f"{row['distinct_readings']} | {'yes' if row['reading_is_unique'] else 'no'} | "
            f"{len(row['unanimous_links'])} |"
        )
    lines += [
        "",
        f"Across {measured['scenarios']} scenarios, {measured['locally_ambiguous_senders']} senders "
        f"were ambiguous on their own constraint and propagation narrowed "
        f"{measured['senders_narrowed_by_propagation']} of them; "
        f"{measured['with_a_unique_reading']} scenario reached a single reading of the amounts.",
        "",
        "Matchings and readings are counted separately on purpose. Two matchings that assign "
        "different output indices but the same amounts are one reading, and the reading is what the "
        "receiver learns — the consolidating scenario has two matchings and one reading.",
        "",
        "Both scenarios are deterministic fixtures and the negotiated payments are supplied rather "
        "than inferred. An external observer holds neither those payments nor the receiver's own "
        "coins, so this is a counterparty capability. A unique reading of the amounts is not "
        "ownership attribution and is not a privacy score.",
        "",
    ]
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
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
