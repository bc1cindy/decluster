"""Thin command-line adapter for the offline dataset catalog API."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .data_catalog import (
    DatasetFetchError,
    DatasetPrepareError,
    DatasetStatus,
    catalog_status,
    fetch_dataset,
    load_dataset_catalog,
    prepare_dataset,
)
from .data_manifest import ManifestError


def _parser():
    parser = argparse.ArgumentParser(prog="decluster-data")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--store", type=Path, default=Path("artifacts"))
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("command", choices=("list", "status", "verify", "fetch", "prepare"))
    parser.add_argument("dataset_id", nargs="?")
    return parser


def _records(command, root, *, dataset_id=None, store=None, replace=False):
    if command == "list":
        return [{
            "id": item.id,
            "kind": item.kind.value,
            "bytes": item.content.bytes,
            "sha256": item.content.sha256,
        } for item in load_dataset_catalog(root)]
    if command in {"status", "verify"}:
        return [{
        "id": check.dataset.id,
        "status": check.status.value,
        "expected": asdict(check.expected),
        "actual": asdict(check.actual) if check.actual is not None else None,
        } for check in catalog_status(root)]
    if not dataset_id:
        raise ManifestError(f"{command}: dataset id is required")
    matches = [dataset for dataset in load_dataset_catalog(root) if dataset.id == dataset_id]
    if not matches:
        raise ManifestError(f"{command}: unknown dataset id {dataset_id!r}")
    if command == "fetch":
        result = fetch_dataset(matches[0], store)
        source_url = result.source_url
    else:
        result = prepare_dataset(matches[0], root, store, replace=replace)
        source_url = None
    return [{
        "id": result.dataset.id,
        "status": result.status.value,
        "path": str(result.path),
        "source_url": source_url,
    }]


def _print(records, *, as_json):
    if as_json:
        print(json.dumps(records, allow_nan=False, separators=(",", ":"), sort_keys=True))
        return
    for record in records:
        if "expected" in record:
            print(f"{record['id']}\t{record['status']}")
        elif "kind" in record:
            print(f"{record['id']}\t{record['kind']}\t{record['bytes']}")
        else:
            print(f"{record['id']}\t{record['status']}\t{record['path']}")


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        store = args.store if args.store.is_absolute() else args.root / args.store
        records = _records(
            args.command, args.root, dataset_id=args.dataset_id, store=store,
            replace=args.replace,
        )
    except (DatasetFetchError, DatasetPrepareError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _print(records, as_json=args.as_json)
    if args.command == "verify" and any(
        record["status"] != DatasetStatus.VERIFIED.value for record in records
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
