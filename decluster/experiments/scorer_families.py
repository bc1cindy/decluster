"""Compare the catalogued, construction-only and decorrelated scorers on one population.

`PAPER.md` reports three rows of AUC and evidence magnitude for the same fingerprint kernel under
three axis sets, and none of them had a run behind it. The numbers were real — this reproduces them
— but a number without a chain is a number a reader has to take on trust.

Only the axis set moves: same transactions, same pair sample, same seed, same consistency. That is
what makes the magnitudes comparable across rows, and it is why the drop from the catalogued family
reads as redundancy and label leakage rather than as a different measurement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ..archive_snapshot import extract_tar_gz
from ..fingerprint_validate import axis_families, load_blkcache
from ..reproducibility import fingerprint_source
from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "scorer-families-v1"
CONSISTENCY = 0.95
PAIR_CAP = 4000
SEED = 0


class VerificationError(ValueError):
    """The stored result differs from a fresh execution."""


def build_artifact(snapshot):
    with TemporaryDirectory(prefix="decluster-families-") as temporary:
        root = extract_tar_gz(snapshot, temporary)
        cache = root / ".blkcache"
        transactions = load_blkcache(str(cache))
        rows = axis_families(transactions, consistency=CONSISTENCY, cap=PAIR_CAP, seed=SEED)
        source = fingerprint_source(str(cache / "*.json"))
        source.update(pattern=".blkcache/*.json", transactions=len(transactions))
    by_family = {row["family"]: row for row in rows}
    catalogued, decorrelated = by_family["catalogued"], by_family["decorrelated"]
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "dataset": "fs-blkcache-2026-09-04-v1",
        "source": source,
        "measurement": {
            "consistency": CONSISTENCY,
            "pair_cap_per_class": PAIR_CAP,
            "seed": SEED,
            "rows": rows,
            "magnitude_fall_from_catalogued_to_decorrelated":
                catalogued["pos_mean"] - decorrelated["pos_mean"],
            "auc_rises_as_axes_are_dropped": decorrelated["auc"] > catalogued["auc"],
        },
        "limitations": [
            "address reuse is a weak and partly feature-dependent ownership proxy",
            "the axis clusters and the address-determined set are measured on this same cache",
            "one selected snapshot is reused for all three families and is not chain-wide",
            "a higher AUC on fewer axes does not establish that the dropped axes carry no signal",
            "evidence magnitudes are rarity bits under a fixed consistency, not calibrated likelihoods",
            "this is attacker-side analysis, not a privacy score",
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


def verify_artifact(artifact, snapshot):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported scorer-family artifact identity")
    measured = build_artifact(snapshot)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    measured = artifact["measurement"]
    rows = {row["family"]: row for row in measured["rows"]}
    lines = [
        "# The same kernel under three axis sets",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"One population of {artifact['source']['transactions']} transactions, one pair sample "
        f"({measured['pair_cap_per_class']} per class, seed {measured['seed']}), one consistency "
        f"({measured['consistency']}). Only the axis set changes.",
        "",
        "| family | axes | AUC | positive mean bits | negative mean bits |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("catalogued", "construction_only", "decorrelated"):
        row = rows[name]
        lines.append(
            f"| {name.replace('_', ' ')} | {row['axes']} | {row['auc']:.4f} | "
            f"{row['pos_mean']:+.2f} | {row['neg_mean']:+.2f} |"
        )
    fall = measured["magnitude_fall_from_catalogued_to_decorrelated"]
    lines += [
        "",
        f"Dropping the redundant axes costs **{fall:.2f} bits** of positive evidence and "
        f"{'raises' if measured['auc_rises_as_axes_are_dropped'] else 'lowers'} the AUC "
        f"({rows['catalogued']['auc']:.4f} to {rows['decorrelated']['auc']:.4f}). The wide model "
        "scores several correlated axes as if they were separate facts; the additive rarity kernel "
        "has no conditional-independence correction, so the magnitude it reports is inflated while "
        "its ranking is not.",
        "",
        "The construction-only family drops the axes the shared input address fixes outright, which "
        "is the part of the score that is the same-owner label restating itself rather than "
        "construction style.",
        "",
        "The axis clusters and the address-determined set were measured on this same cache, so the "
        "families are not an out-of-sample test. A higher AUC on fewer axes does not show the "
        "dropped axes carry no signal, and none of these numbers is a privacy score.",
        "",
    ]
    return "\n".join(lines)


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("reproduce", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--artifact", required=True)
        command.add_argument("--markdown", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if args.command == "reproduce":
        artifact = build_artifact(args.snapshot)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(load_artifact(args.artifact), args.snapshot)
        if Path(args.markdown).read_text(encoding="utf-8") != render_markdown(artifact):
            raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
