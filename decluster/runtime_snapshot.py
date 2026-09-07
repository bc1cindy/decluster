"""The runtime snapshot every evidence bundle pins as its source.

`reproduce` extracts this archive and runs *its* code, so the archive — not the working tree — is
what a bundle's reproduction actually exercises. An archive that lags the tree makes the gate
verify a revision nobody ships.

Entries carry a zero timestamp and no ownership, so the same revision always produces the same
bytes and the digest a bundle pins is a function of content alone.

`--repoint` does the rest of the move: every `reproduction/*/environment.json`, every run manifest's
`code.revision` and every bundle's source blob name follow the new archive, and the superseded one
is removed. Done by hand it is four steps in a required order, and skipping any of them leaves a
record describing a runtime nobody ships. `decluster-bundle sync` then refreshes the identities.
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import tarfile
from pathlib import Path

PREFIX = "decluster"

# The reproduction surface: the package and what it reads at run time. Datasets are materialised
# from the content store instead, and `results/generated` is an output, not an input.
INCLUDED = (
    "decluster",
    "catalog",
    "examples",
    "results/artifacts",
    "tests/fixtures/conservation_round_three.json",
    "pyproject.toml",
    "LICENSE",
)


def _git(*args, root):
    return subprocess.run(
        ("git", *args), cwd=root, capture_output=True, check=True
    ).stdout


def revision_id(revision, root):
    return _git("rev-parse", revision, root=root).decode().strip()


def tracked_paths(revision, root):
    """Every file the snapshot covers at `revision`, with its git mode, in a stable order."""
    listing = _git("ls-tree", "-r", revision, "--", *INCLUDED, root=root).decode()
    entries = {}
    for line in listing.splitlines():
        if not line:
            continue
        metadata, path = line.split("\t", 1)
        entries[path] = 0o755 if metadata.split()[0] == "100755" else 0o644
    return dict(sorted(entries.items()))


def _walk(paths):
    """Names in archive order: one sorted sequence with each directory before its contents."""
    directories = set()
    for path in paths:
        parts = path.split("/")[:-1]
        for index in range(len(parts)):
            directories.add("/".join(parts[: index + 1]))
    return [(name, name in directories) for name in sorted(directories | set(paths))]


def _entry(name, *, directory=False, size=0, mode=0o644):
    info = tarfile.TarInfo(f"{PREFIX}/{name}" if name else PREFIX)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.mode = 0o755 if directory else mode
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.size = size
    return info


def build(revision="HEAD", root=".", out_dir="sources"):
    """Write `sources/decluster-<short>-runtime.tar` for `revision`, deterministically."""
    root = Path(root).resolve()
    full = revision_id(revision, root)
    paths = tracked_paths(full, root)
    if not paths:
        raise ValueError(f"no tracked files under {INCLUDED} at {revision}")

    destination = Path(root, out_dir, f"{PREFIX}-{full[:7]}-runtime.tar")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w", format=tarfile.USTAR_FORMAT) as archive:
        archive.addfile(_entry("", directory=True))
        for name, is_directory in _walk(paths):
            if is_directory:
                archive.addfile(_entry(name, directory=True))
                continue
            payload = _git("show", f"{full}:{name}", root=root)
            entry = _entry(name, size=len(payload), mode=paths[name])
            archive.addfile(entry, io.BytesIO(payload))
    return destination, full, len(paths)


def repoint(root, archive, revision, out_dir="sources"):
    """Point every record at `archive`, then drop the archives it supersedes."""
    root = Path(root)
    name = f"{out_dir}/{archive.name}"
    moved = []
    for environment in sorted(root.glob("reproduction/*/environment.json")):
        record = json.loads(environment.read_text())
        if record.get("source_archive") == name:
            continue
        record["source_archive"] = name
        environment.write_text(json.dumps(record, indent=2) + "\n")
        moved.append(str(environment.relative_to(root)))
    for manifest in sorted(root.glob("catalog/runs/*.json")):
        record = json.loads(manifest.read_text())
        if record["code"]["revision"] == revision:
            continue
        manifest.write_text(manifest.read_text().replace(
            f'"revision": "{record["code"]["revision"]}"', f'"revision": "{revision}"', 1))
        moved.append(str(manifest.relative_to(root)))
    for index in sorted(root.glob("releases/*.bundle.json")):
        record = json.loads(index.read_text())
        touched = False
        for blob in record["blobs"]:
            if blob["role"] == "source" and blob["name"] != name:
                blob["name"] = name
                touched = True
        if touched:
            index.write_text(json.dumps(record, indent=2) + "\n")
            moved.append(str(index.relative_to(root)))
    superseded = [p for p in Path(root, out_dir).glob(f"{PREFIX}-*-runtime.tar")
                  if p.name != archive.name]
    for stale in superseded:
        stale.unlink()
    return moved, [p.name for p in superseded]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out-dir", default="sources")
    parser.add_argument("--repoint", action="store_true",
                        help="point every environment, run manifest and bundle at the new archive")
    arguments = parser.parse_args(argv)
    path, revision, count = build(arguments.revision, arguments.root, arguments.out_dir)
    print(f"{path}  {revision[:7]}  {count} files")
    if arguments.repoint:
        moved, superseded = repoint(arguments.root, path, revision, arguments.out_dir)
        print(f"repointed {len(moved)} records; removed {len(superseded)} superseded archive(s)")
        print("run `decluster-bundle sync` to refresh the identities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
