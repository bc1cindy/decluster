"""A reader opening a results document has to be told what backs it, in the document.

`REPRODUCIBILITY.md` says the five states are indexed centrally and that "per-doc `Reproducibility /
provenance` footers point back here". Thirty-three documents said nothing at all, and nothing noticed:
the central index is not reachable from the page a reader is on, so a number band-pinned on committed
data and one from an uncommitted data-run read exactly alike.

Three answers count, because the repository already keeps provenance in three places: a footer naming
the state, a canonical run manifest the document points at, or a legacy manifest recorded for it.
`UNFILED` is the honest fourth — better than a guessed state, and unlike silence it is visible to the
reader and counted here, so the backlog shrinks only when someone reads a document and files it.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / "results").glob("RESULTS-*.md"))
FOOTER = re.compile(r"^#+ *(?:reproduc\w*|data and reproducibility)(?: */ *provenance)? *$", re.M | re.I)
RUN = re.compile(r"catalog/runs/[\w.-]+\.json")
STATE = re.compile(r"\bstate [1-5]\b", re.I)
UNFILED = "Not yet filed against `results/REPRODUCIBILITY.md`"
# A footer states the level in substance when it points at what pins the number.
EVIDENCE = re.compile(r"tests?/[\w./-]+|test_[\w]+\.py|data/[\w./-]+|bigquery/[\w./-]+\.sql")
LEGACY = {p.stem + ".md" for p in (ROOT / "results" / "manifests").glob("*.json")}

# Documents nobody has assigned an evidence state yet. Filing one is deliberate work; so is adding to
# the pile, which is what the ceiling stops.
UNFILED_CEILING = 29


def _footer(doc):
    text = doc.read_text()
    match = FOOTER.search(text)
    return text[match.end():] if match else None


def test_every_results_document_says_what_backs_it():
    assert DOCS, "no results document was found; this gate is measuring nothing"
    silent = [d.name for d in DOCS
              if _footer(d) is None and not RUN.search(d.read_text()) and d.name not in LEGACY]
    assert not silent, (
        "these send a reader numbers with no statement of what backs them:\n  "
        + "\n  ".join(silent)
        + "\nAdd a `## Reproducibility / provenance` section, or point at the run manifest."
    )


def test_every_footer_names_a_state_or_declares_none_assigned():
    """Naming the state is one way; pointing at the fixture, test or query that pins it is another."""
    vague = [d.name for d in DOCS
             if (body := _footer(d)) is not None
             and not STATE.search(body) and UNFILED not in body
             and not EVIDENCE.search(body)
             and not RUN.search(d.read_text()) and d.name not in LEGACY]
    assert not vague, (
        "these carry a footer that names neither a state nor a manifest, and does not declare the\n"
        "state unassigned:\n  " + "\n  ".join(vague))


def test_the_unfiled_backlog_does_not_grow():
    """A ceiling, not a target: it falls when a document is read and filed, never quietly."""
    unfiled = [d.name for d in DOCS if (body := _footer(d)) is not None and UNFILED in body]
    assert len(unfiled) <= UNFILED_CEILING, (
        f"{len(unfiled)} documents are unfiled; the ceiling is {UNFILED_CEILING}. "
        "File the new one against REPRODUCIBILITY.md rather than raising this.")
