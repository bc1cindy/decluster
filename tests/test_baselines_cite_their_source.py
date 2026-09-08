"""A reimplementation that does not name what it reimplements is not checkable.

Half the modules under `decluster/baselines/` were reachable from no claim that named a source, and
five of those six cited nothing in the file either — no identifier, no year, no note. A reader
opening `kelen_seres_graphs.py` could not tell which paper, or which edition of it, the code was
supposed to agree with, and neither could a reviewer.

The rule is the weakest one that fixes that: the module says which catalogue entry it implements,
and the entry exists. Fidelity to the source is a separate question this cannot answer.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BASELINES = sorted(p for p in (ROOT / "decluster" / "baselines").glob("*.py")
                   if p.stem != "__init__")
REFERENCE = re.compile(r"`([a-z0-9-]+)` in `catalog/ctp-sources\.json`")


def _docstring(path):
    text = path.read_text()
    if not text.startswith('"""'):
        return ""
    return text[3:text.index('"""', 3)]


@pytest.fixture(scope="module")
def registered():
    catalogue = json.loads((ROOT / "catalog" / "ctp-sources.json").read_text())
    return {source["id"] for source in catalogue["sources"]}


def test_every_baseline_names_the_work_it_reimplements(registered):
    assert BASELINES, "no baseline module was found; this gate is measuring nothing"
    silent = [p.name for p in BASELINES if not REFERENCE.search(_docstring(p))]
    assert not silent, (
        "these reimplement a published algorithm without naming which:\n  " + "\n  ".join(silent)
        + "\nAdd `Source: `<id>` in `catalog/ctp-sources.json`` to the module docstring.")


def test_the_source_a_baseline_names_is_registered(registered):
    dangling = sorted({identifier for path in BASELINES
                       for identifier in REFERENCE.findall(_docstring(path))
                       if identifier not in registered})
    assert not dangling, f"baselines cite catalogue entries that do not exist: {dangling}"
