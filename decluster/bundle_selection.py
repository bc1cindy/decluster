"""Which evidence bundles a change can actually reach.

The reproduction gate reexecutes every committed bundle in a pinned environment, and one run in it
takes half an hour. Running all sixty-odd for an edit that two of them can see is why the gate gets
skipped, and a gate nobody runs proves nothing. This narrows it to the bundles a change can reach,
by two rules and one blanket:

  blobs        a bundle pins its manifest, results, datasets, lockfile and environment by digest.
               Touch one and that bundle is selected. The source archive is excluded: every bundle
               pins it, so it would select all of them on any code edit at all.
  imports      a run is one module, `python -m decluster.experiments.<name>`. A changed `.py`
               selects the runs whose entry module reaches it through intra-package imports.
  everything   any other change inside the archived surface — a catalog file, a fixture,
               `pyproject.toml` — is read at run time rather than imported, so it selects all.

The import closure is static: `importlib` and other deferred lookups are invisible to it, so a
narrowed run is evidence about the bundles it names and not a licence to skip the full gate before
publishing.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path

from .runtime_snapshot import INCLUDED

PACKAGES = ("decluster", "examples")
# Precisely pinned by rule one, so the blanket must not claim them as well.
PINNED_SUBTREES = ("catalog/runs/", "results/artifacts/")
NOTHING = "no-bundle-selected"


def changed_paths(root=".", base="HEAD"):
    """Repository-relative paths that differ from `base`, including uncommitted work."""
    result = subprocess.run(
        ("git", "diff", "--name-only", base), cwd=root, capture_output=True, check=True
    )
    return {line for line in result.stdout.decode().splitlines() if line}


def _module_path(root, dotted):
    if dotted.split(".")[0] not in PACKAGES:
        return None
    stem = Path(root, *dotted.split("."))
    for candidate in (stem.with_suffix(".py"), stem / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _imported(module, tree):
    """Every dotted name `tree` imports, with relative imports resolved against `module`."""
    parts = module.split(".")
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = parts[: len(parts) - node.level] if node.level else []
            base = ".".join([*prefix, *([node.module] if node.module else [])])
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def module_closure(root, module):
    """The `.py` files `module` reaches through intra-package imports, itself included."""
    root = Path(root)
    seen, pending, files = set(), [module], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        path = _module_path(root, current)
        if path is None:
            continue
        files.add(str(path.relative_to(root)))
        pending.extend(_imported(current, ast.parse(path.read_text(encoding="utf-8"))))
    return files


def _entry_module(root, run_id):
    argv = json.loads(Path(root, "catalog", "runs", f"{run_id}.json").read_text())["command"]["argv"]
    return argv[argv.index("-m") + 1]


def _in_archive(path):
    return any(path == name or path.startswith(f"{name}/") for name in INCLUDED)


def affected(root=".", changed=()):
    """Every bundle id a changed path can reach, with the rule that selected it."""
    root = Path(root)
    changed = set(changed)
    blanket = {
        path for path in changed
        if _in_archive(path)
        and not path.endswith(".py")
        and not path.startswith(PINNED_SUBTREES)
    }
    sources = {path for path in changed if path.endswith(".py") and _in_archive(path)}

    selected = {}
    for index in sorted(Path(root, "releases").glob("*.bundle.json")):
        bundle = json.loads(index.read_text())
        pinned = {blob["name"] for blob in bundle["blobs"] if blob["role"] != "source"}
        reason = None
        if changed & pinned:
            reason = "blob"
        elif blanket:
            reason = "archive"
        elif sources and any(
            sources & module_closure(root, _entry_module(root, run)) for run in bundle["runs"]
        ):
            reason = "import"
        if reason:
            selected[bundle["id"]] = reason
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--path", action="append", default=[],
                        help="use these paths instead of asking git")
    parser.add_argument("--pytest", action="store_true",
                        help="print the -k expression that selects their reproduction tests")
    arguments = parser.parse_args(argv)
    changed = set(arguments.path) or changed_paths(arguments.root, arguments.base)
    selected = affected(arguments.root, changed)
    if arguments.pytest:
        # An empty -k expression selects every test, so say "nothing" in a way pytest can read.
        print(" or ".join(sorted(selected)) if selected else NOTHING)
        return 0
    for identifier, reason in sorted(selected.items()):
        print(f"  {reason:8} {identifier}")
    print(f"{len(selected)} of {len(list(Path(arguments.root, 'releases').glob('*.bundle.json')))}"
          " bundles selected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
