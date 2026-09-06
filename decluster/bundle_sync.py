"""Bring the content store and the bundle indexes back in step with the tree.

A bundle pins each blob by name, byte count and digest, and the same bytes are kept in
`artifacts/sha256/`. Editing a tracked file that a bundle ships therefore has to move three things
at once, and doing it by hand goes wrong in ways the suite only half catches: a digest updated
without its byte count still verifies against the store, and a stored blob nobody references stays
behind until the completeness test notices.

Two rules the procedure has to respect, both learned by breaking them:

  store-only blobs   a blob whose name is not in the tree — the built `dss` wheel — keeps the
                     identity it has. It is not missing; it was never a tracked file.
  orphans last       a blob is removed from the store only after every index has been rewritten,
                     because until then "referenced" is not yet known.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

INDEX_DIR = "releases"
STORE_DIR = "artifacts/sha256"


@dataclass(frozen=True)
class Change:
    kind: str
    name: str
    detail: str


def _identity(path):
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def _indexes(root):
    return sorted(Path(root, INDEX_DIR).glob("*.bundle.json"))


def _stored(root):
    store = Path(root, STORE_DIR)
    return {p.parent.name + p.name: p for p in store.glob("*/*") if p.is_file()}


def synchronise(root=".", *, write=True):
    """Return the changes the store and indexes need, applying them unless `write` is false."""
    root = Path(root)
    changes = []

    for index in _indexes(root):
        bundle = json.loads(index.read_text())
        touched = False
        for blob in bundle["blobs"]:
            source = root / blob["name"]
            if not source.is_file():
                continue                       # store-only blob: its identity stands
            size, digest = _identity(source)
            if (size, digest) == (blob["bytes"], blob["sha256"]):
                continue
            changes.append(Change("identity", blob["name"],
                                  f"{blob['bytes']}/{blob['sha256'][:12]} -> {size}/{digest[:12]}"))
            blob["bytes"], blob["sha256"] = size, digest
            touched = True
        if touched and write:
            index.write_text(json.dumps(bundle, indent=2) + "\n")

    referenced = {}
    for index in _indexes(root):
        for blob in json.loads(index.read_text())["blobs"]:
            referenced[blob["sha256"]] = blob["name"]

    stored = _stored(root)
    for digest, name in sorted(referenced.items(), key=lambda item: item[1]):
        if digest in stored:
            continue
        source = root / name
        if not source.is_file():
            changes.append(Change("unavailable", name, f"{digest[:12]} is in no store and no tree"))
            continue
        changes.append(Change("stored", name, digest[:12]))
        if write:
            target = Path(root, STORE_DIR, digest[:2], digest[2:])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())

    for digest in sorted(set(stored) - set(referenced)):
        changes.append(Change("orphaned", stored[digest].name, digest[:12]))
        if write:
            stored[digest].unlink()

    return tuple(changes)


def unresolved(changes):
    """The changes `synchronise` could not carry out on its own."""
    return tuple(change for change in changes if change.kind == "unavailable")
