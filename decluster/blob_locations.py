"""Give each bundle blob a canonical URL, but only one that actually resolves.

A bundle without locations bootstraps from the local store and nowhere else, so a reader who has
the checkout can verify it and a reader who has the index cannot. Filling the field in is cheap;
filling it in *honestly* is the constraint, because a canonical URL names a revision, and a revision
that has not been pushed is a link that 404s. Declaring one would be the same defect this
repository keeps finding elsewhere — a record asserting something nobody checked.

So the rule here is content-addressed, not name-addressed: a blob gets a URL only when the file at
the named revision hashes to the digest the bundle pins, and only when that revision is an ancestor
of the published branch. Everything else is left null and counted, which is the honest state until
the branch is pushed.

`--check` reports what could be filled in and what could not, so the gap is visible rather than
mistaken for a decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

RAW = "https://github.com/bc1cindy/decluster/raw/{revision}/{path}"
REVISION = re.compile(r"/raw/([0-9a-f]{40})/(.+)$")


def _git(*args, root="."):
    return subprocess.run(("git", *args), cwd=root, capture_output=True)


def is_ancestor(revision, published, root="."):
    return _git("merge-base", "--is-ancestor", revision, published, root=root).returncode == 0


def digest_at(revision, path, root="."):
    result = _git("show", f"{revision}:{path}", root=root)
    if result.returncode:
        return None
    return hashlib.sha256(result.stdout).hexdigest()


def resolvable(blob, revision, published, root="."):
    """Whether a URL at `revision` would serve exactly the bytes this blob pins."""
    return (is_ancestor(revision, published, root=root)
            and digest_at(revision, blob["name"], root=root) == blob["sha256"])


def audit(root=".", published="origin/master"):
    """Every blob, and whether its declared location resolves or one could be declared."""
    rows = []
    for index in sorted(Path(root, "releases").glob("*.bundle.json")):
        for blob in json.loads(index.read_text())["blobs"]:
            declared = blob["locations"]["canonical"]
            state = "absent"
            if declared:
                match = REVISION.search(declared)
                state = ("resolves" if match and resolvable(blob, match.group(1), published, root)
                         else "dangling")
            elif digest_at(published, blob["name"], root=root) == blob["sha256"]:
                state = "available"
            rows.append({"bundle": index.stem, "name": blob["name"], "state": state})
    return rows


def apply(root=".", published="origin/master"):
    """Fill in what resolves at `published`, and clear what does not. Returns the changes."""
    revision = _git("rev-parse", published, root=root).stdout.decode().strip()
    changes = []
    for index in sorted(Path(root, "releases").glob("*.bundle.json")):
        bundle = json.loads(index.read_text())
        touched = False
        for blob in bundle["blobs"]:
            declared = blob["locations"]["canonical"]
            fits = digest_at(revision, blob["name"], root=root) == blob["sha256"]
            if declared:
                match = REVISION.search(declared)
                if match and resolvable(blob, match.group(1), published, root):
                    continue                       # an older public revision still serves it
                if not fits:
                    blob["locations"]["canonical"] = None
                    changes.append(("cleared", blob["name"]))
                    touched = True
                    continue
            if fits and not declared:
                blob["locations"]["canonical"] = RAW.format(revision=revision, path=blob["name"])
                changes.append(("declared", blob["name"]))
                touched = True
        if touched:
            index.write_text(json.dumps(bundle, indent=2) + "\n")
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--published", default="origin/master")
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.check:
        rows = audit(arguments.root, arguments.published)
        counts = {}
        for row in rows:
            counts[row["state"]] = counts.get(row["state"], 0) + 1
        for state in ("resolves", "available", "absent", "dangling"):
            print(f"  {state}: {counts.get(state, 0)}")
        for row in rows:
            if row["state"] == "dangling":
                print(f"    dangling  {row['bundle']}  {row['name']}")
        return 1 if counts.get("dangling") else 0
    for kind, name in apply(arguments.root, arguments.published):
        print(f"  {kind}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
