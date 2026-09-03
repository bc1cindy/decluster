"""Thin command-line adapter for evidence bundle verification and bootstrap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .data_manifest import ManifestError
from .evidence_bundle import (
    BlobStatus,
    BundleBootstrapError,
    BundleReproductionError,
    ReproductionStatus,
    assess_reproduction_readiness,
    bootstrap_bundle,
    load_bundle,
    reproduce_bundle,
    verify_bundle,
)


def _parser():
    parser = argparse.ArgumentParser(prog="decluster-bundle")
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--store", type=Path, default=Path("artifacts"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--work", type=Path)
    parser.add_argument("command", choices=("verify", "bootstrap", "readiness", "reproduce"))
    return parser


def _verification_records(bundle, store):
    return [{
        "name": check.blob.name,
        "status": check.status.value,
        "bytes": check.blob.content.bytes,
        "sha256": check.blob.content.sha256,
    } for check in verify_bundle(bundle, store)]


def _bootstrap_records(bundle, store, root, *, replace):
    return [{
        "name": result.blob.name,
        "acquisition": result.acquisition.value,
        "materialization": result.materialization.value,
        "path": str(result.path),
        "source_url": result.source_url,
    } for result in bootstrap_bundle(bundle, store, root, replace=replace)]


def _print(records, as_json):
    if as_json:
        print(json.dumps(records, allow_nan=False, separators=(",", ":"), sort_keys=True))
        return
    for record in records:
        if "issues" in record:
            print(f"{record['bundle']}\t{record['status']}")
            for issue in record["issues"]:
                print(f"{issue['kind']}\t{issue['subject']}\t{issue['detail']}")
            continue
        state = record.get("status") or (
            f"{record['acquisition']}/{record['materialization']}"
        )
        print(f"{record['name']}\t{state}")


def _readiness_record(bundle, store, root):
    readiness = assess_reproduction_readiness(bundle, store, root)
    return readiness, {
        "bundle": bundle.id,
        "status": readiness.status.value,
        "issues": [
            {"kind": issue.kind.value, "subject": issue.subject, "detail": issue.detail}
            for issue in readiness.issues
        ],
    }


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        bundle = load_bundle(args.index)
        readiness = None
        if args.command == "verify":
            records = _verification_records(bundle, args.store)
        elif args.command == "bootstrap":
            records = _bootstrap_records(
                bundle, args.store, args.root, replace=args.replace,
            )
        elif args.command == "readiness":
            readiness, record = _readiness_record(bundle, args.store, args.root)
            records = [record]
        else:
            if args.work is None:
                parser = _parser()
                parser.error("--work is required for reproduce")
            records = [{"name": str(path), "status": "reproduced"}
                       for path in reproduce_bundle(bundle, args.root, args.work)]
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except BundleBootstrapError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except BundleReproductionError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _print(records, args.as_json)
    if args.command == "verify" and any(
        record["status"] != BlobStatus.VERIFIED.value for record in records
    ):
        return 1
    if readiness is not None and readiness.status is ReproductionStatus.BLOCKED:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
