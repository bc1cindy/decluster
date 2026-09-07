"""Score the merged anchor's false Cake-to-sender edge under every axis set the paper compares.

`PAPER.md` §4 turns on one named edge: the three-axis engine refuses it, the twenty-three-axis
library resurrects it past the engine's `link_above` threshold, and dropping the redundant axes
brings it back below. The paper calls that measured rather than asserted, and it was — by a script
reading two transactions out of a gitignored cache, which is not something a reader can rerun.

So the two transactions are committed as a fixture and the comparison is a run. `scorer-families`
measures the same three axis sets over a population; this measures them on the one edge the
argument names, which is a different question: a mean says what the families do on average, and
this says what they did to the case the design decision was made on.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..combiner import Combiner
from ..fingerprint_validate import (
    LibraryScorer,
    construction_only_scorer,
    decorrelated_scorer,
)
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "anchor-axis-families-v1"
DEFAULT_DATASET = "tests/fixtures/merged_anchor_931d6627.json"
LINK_ABOVE = 4.0


class VerificationError(ValueError):
    """The dataset or stored result violates this experiment's contract."""


def _load(path):
    try:
        fixture = json.loads(Path(path).read_text(encoding="utf-8"))
        cake = fixture["transactions"]["cake"]
        sender = fixture["transactions"]["sender"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise VerificationError(f"cannot read anchor fixture {path}: {exc}") from exc
    if not cake.get("txid") or not sender.get("txid"):
        raise VerificationError(f"{path}: both anchor transactions must carry a txid")
    return fixture, cake, sender


def _rows(scorer, sender, cake):
    _score, rows = scorer.score(sender, cake, explain=True)
    return [
        {"axis": name, "sender": str(a), "cake": str(b),
         "bits": None if weight is None else weight}
        for name, a, b, weight in rows
    ]


def build_artifact(dataset=DEFAULT_DATASET):
    fixture, cake, sender = _load(dataset)
    engine = Combiner.from_library()
    families = {
        "engine_three_axis": (engine, None),
        "catalogued": (LibraryScorer(), None),
        "construction_only": (construction_only_scorer(), None),
        "decorrelated": (decorrelated_scorer(), None),
    }
    scores = {}
    for name, (scorer, _) in families.items():
        score = scorer.score(sender, cake)
        if isinstance(score, tuple):
            score = score[0]
        scores[name] = {
            "axes": len(getattr(scorer, "axes", ())),
            "bits": score,
            "verdict": "link" if score > 0 else "refuse",
            "past_link_above": score > LINK_ABOVE,
        }
    catalogued = _rows(LibraryScorer(), sender, cake)
    positive = [row for row in catalogued if row["bits"] is not None and row["bits"] > 0]
    negative = [row for row in catalogued if row["bits"] is not None and row["bits"] < 0]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "merged-anchor-931d6627-v1",
        "anchor": fixture["anchor"],
        "edge": {"sender": sender["txid"], "cake": cake["txid"]},
        "measurement": {
            "link_above": LINK_ABOVE,
            "families": scores,
            "redundancy_bits": scores["catalogued"]["bits"] - scores["decorrelated"]["bits"],
            "catalogued_axes_scored": sum(1 for row in catalogued if row["bits"] is not None),
            "catalogued_axes_abstaining": sum(1 for row in catalogued if row["bits"] is None),
            "positive_axes": len(positive),
            "negative_axes": len(negative),
            "negative_bits_total": sum(row["bits"] for row in negative),
            "positive_bits_total": sum(row["bits"] for row in positive),
            "per_axis": catalogued,
        },
        "limitations": [
            "one named edge, chosen because the design decision was argued on it",
            "the same-owner reading of this edge is the paper's, not an independent label",
            "a score past link_above is what the engine would do, not what it does: the engine "
            "scores three axes",
            "the library weights come from a population that was not preserved; "
            "library-calibration-v1 measures how far they sit from the one that was",
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


def verify_artifact(artifact, dataset=DEFAULT_DATASET):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported anchor-axis-family artifact identity")
    measured = build_artifact(dataset)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    families = measured["families"]
    lines = [
        f"# The merged anchor's false edge under four axis sets",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"One edge — the sender's funding transaction against the Cake one, on anchor "
        f"`{artifact['anchor']}`. The engine's refusal threshold is `link_above = "
        f"{measured['link_above']}`.",
        "",
        "| axis set | axes | bits | verdict | past link_above |",
        "|---|---:|---:|---|---|",
    ]
    for name in ("engine_three_axis", "catalogued", "construction_only", "decorrelated"):
        row = families[name]
        lines.append(
            f"| {name.replace('_', ' ')} | {row['axes']} | {row['bits']:+.2f} | {row['verdict']} | "
            f"{'yes' if row['past_link_above'] else 'no'} |"
        )
    lines += [
        "",
        f"The catalogued model resurrects the edge at {families['catalogued']['bits']:+.2f} bits, "
        f"well past the threshold. Dropping one representative per correlated cluster leaves "
        f"{families['decorrelated']['bits']:+.2f} — **{measured['redundancy_bits']:.2f} bits of the "
        "score were copies of evidence already counted**, and what remains sits below the "
        "threshold, so the wide model's failure here is duplication rather than width.",
        "",
        f"Of the {measured['catalogued_axes_scored']} axes that scored, "
        f"{measured['negative_axes']} argue against the pairing "
        f"({measured['negative_bits_total']:+.2f} bits between them) and "
        f"{measured['positive_axes']} argue for it "
        f"({measured['positive_bits_total']:+.2f}); "
        f"{measured['catalogued_axes_abstaining']} abstain. The discriminating axes still refuse — "
        "they are outvoted by low-entropy policy axes that two ordinary wallets share, summed under "
        "a kernel that assumes they are independent.",
        "",
        "This is one edge, chosen because the design decision was argued on it, and its same-owner "
        "reading is the paper's rather than an independent label. The library weights come from a "
        "population that was not preserved; `library-calibration-v1` measures how far they sit from "
        "the one that was.",
        "",
    ]
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", required=True)
        command.add_argument("--markdown", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact(args.dataset)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), args.dataset)
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
