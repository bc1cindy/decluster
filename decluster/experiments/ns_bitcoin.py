"""Reproduce N-S propagation across adjacent Bitcoin observation windows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from examples import ns_bitcoin_views as legacy

from ..result_artifacts import canonical_json_bytes, write_canonical_json

EXPERIMENT_ID = "ns-bitcoin-v1"
LEFT = "data/ns-bitcoin-2016-v1/left-391992-392111.ndjson.gz"
RIGHT = "data/ns-bitcoin-2016-v1/right-392112-392231.ndjson.gz"


class VerificationError(ValueError):
    """A stored result differs from a fresh execution."""


def build_artifact(left=LEFT, right=RIGHT):
    args = legacy.build_parser().parse_args(["--left", str(left), "--right", str(right)])
    report = legacy.build_report(args)
    report["views"]["left"]["path"] = LEFT
    report["views"]["right"]["path"] = RIGHT
    return {
        "schema_version": 1,
        "experiment": EXPERIMENT_ID,
        "corpus": "adjacent public Bitcoin block windows",
        "report": report,
        "limitations": [
            "no independent gradeable seeds were found in these windows",
            "the measured sweep uses seeds sampled from withheld correspondence",
            "operational precision is approximately one percent",
            "the observation windows are not representative of the whole chain",
            "this does not reproduce the Twitter, Flickr, or LiveJournal experiments",
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


def verify_artifact(artifact, *, left=LEFT, right=RIGHT):
    if artifact.get("schema_version") != 1 or artifact.get("experiment") != EXPERIMENT_ID:
        raise VerificationError("unsupported N-S Bitcoin artifact identity")
    measured = build_artifact(left, right)
    if canonical_json_bytes(artifact) != canonical_json_bytes(measured):
        raise VerificationError("artifact differs from a fresh experiment execution")
    return measured


def render_markdown(artifact):
    report = artifact["report"]
    runs = report["runs"]
    best = max(runs, key=lambda run: run["attack"]["precision"])
    return "\n".join([
        "# N-S propagation on Bitcoin views",
        "",
        "Generated from the canonical experiment artifact. Do not edit manually.",
        "",
        f"The two windows contain {report['views']['left']['transactions']:,} and "
        f"{report['views']['right']['transactions']:,} transactions. No independent "
        "gradeable seed was found.",
        "",
        f"The seed-assisted sweep's highest precision is "
        f"{best['attack']['precision']:.4%}, with coverage "
        f"{best['attack']['coverage']:.4%}.",
        "",
        "The sweep does not establish an independently seeded attack and is not a "
        "reproduction of the published social-network corpora.",
        "",
    ])


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", default=LEFT)
    parser.add_argument("--right", default=RIGHT)
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
        artifact = build_artifact(args.left, args.right)
        write_canonical_json(args.artifact, artifact)
        destination = Path(args.markdown)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_markdown(artifact), encoding="utf-8")
    else:
        artifact = verify_artifact(
            load_artifact(args.artifact), left=args.left, right=args.right
        )
        if args.markdown is not None:
            actual = Path(args.markdown).read_text(encoding="utf-8")
            if actual != render_markdown(artifact):
                raise VerificationError("Markdown differs from canonical rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
