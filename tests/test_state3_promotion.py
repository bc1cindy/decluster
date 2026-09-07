"""State 3 says a claim becomes reproducible once a small query output is committed. This is the wiring.

`REPRODUCIBILITY.md` state 3 listed four claims as "run the query, commit the small output as a
fixture, and the number becomes band-pinnable". Nothing connected that sentence to anything: the
fixture had no agreed path, so committing one would have pinned nothing until somebody also wrote the
test. Here the test exists first and skips, naming the query to run and the file to write, so the
promotion is a single commit rather than a small project.

A skip is loud on purpose — it names what went unchecked, the way `test_results_manifests.py` does.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

SLOTS = {
    "persistence-curve": ("bigquery/persistence_curve.sql", "persistence_curve.json",
                          "RESULTS-persistence-curve.md", "5-row aggregate"),
    "slice-gate": ("bigquery/slice_gate.sql", "slice_gate.json",
                   "RESULTS-slice-gate-2026.md", "three aggregates, one per section"),
    # The shipped library bits came from a ~105k uniform sample that no longer exists; PAPER.md §5
    # states them and `test_paper_numbers.py` carries "105,000" as unbacked. A fresh small sample
    # recalibrates them on data a reader has. `library-calibration-v1` does not close this: it
    # measures divergence against a different population and says so.
    "fingerprint-calibration": ("bigquery/sample_small.sql", "fingerprint_calibration.ndjson.gz",
                                "PAPER.md", "15k sampled transactions"),
}

COLUMNS = ("width", "core_vertices", "mean_degree_a",
           "neighbour_persistence", "mean_per_vertex_persistence", "with_3plus_surviving")


def _published_rows(doc, columns):
    """The document's own table, as the query's columns name them."""
    body = (ROOT / "results" / doc).read_text()
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if len(cells) != len(columns) or not re.match(r"^[\d ]+ day", cells[0]):
            continue
        values = [int(re.match(r"(\d+)", cells[0]).group(1))]
        values += [float(c.replace(" ", "")) for c in cells[1:]]
        rows.append(dict(zip(columns, values)))
    return rows


@pytest.mark.parametrize("claim", sorted(SLOTS))
def test_the_state_three_fixture_is_committed(claim):
    query, fixture, doc, shape = SLOTS[claim]
    if not (FIXTURES / fixture).is_file():
        pytest.skip(f"{claim}: NOT pinned — run `{query}` ({shape}) and commit its output as "
                    f"tests/fixtures/{fixture}; {doc} is a data-run until then")


def test_the_persistence_curve_table_is_the_committed_query_output():
    """The worked example: once the fixture lands, the published table has to equal it."""
    fixture = FIXTURES / SLOTS["persistence-curve"][1]
    if not fixture.is_file():
        pytest.skip("persistence-curve: fixture absent, so the published table is unchecked")
    recorded = json.loads(fixture.read_text())
    published = _published_rows(SLOTS["persistence-curve"][2], COLUMNS)
    assert published, "the document's table did not parse; the gate would pass on nothing"
    by_width = {row["width"]: row for row in recorded}
    for row in published:
        expected = by_width.get(row["width"])
        assert expected is not None, f"width {row['width']} is published but not in the query output"
        for column in COLUMNS:
            assert abs(float(expected[column]) - row[column]) < 0.5 * 10 ** -3, (
                f"width {row['width']}: {column} is {row[column]} in the document, "
                f"{expected[column]} in the committed query output")

SEED_COLUMNS = ("k", "in_top_k_both", "precision_at_k")


def _numeric_rows(doc, width):
    """Every table row in `doc` with `width` numeric cells, as floats."""
    rows = []
    for line in (ROOT / "results" / doc).read_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("\u202f", "").replace(" ", "") for c in line.strip().strip("|").split("|")]
        if len(cells) != width or not all(re.fullmatch(r"-?[\d.]+", c) for c in cells):
            continue
        rows.append([float(c) for c in cells])
    return rows


def test_the_slice_gate_seed_supply_table_is_the_committed_query_output():
    """The go/no-go table a reader is asked to trust, against the query that produced it."""
    fixture = FIXTURES / SLOTS["slice-gate"][1]
    if not fixture.is_file():
        pytest.skip("slice-gate: fixture absent, so the published tables are unchecked")
    recorded = {row["k"]: row for row in json.loads(fixture.read_text())["seed_supply"]}
    published = _numeric_rows(SLOTS["slice-gate"][2], 3)
    assert len(published) == len(recorded), (
        f"{len(published)} seed-supply rows are published, {len(recorded)} were measured")
    for k, in_both, precision in published:
        row = recorded.get(int(k))
        assert row is not None, f"top-{int(k)} is published but not in the query output"
        assert row["in_top_k_both"] == int(in_both), (
            f"top-{int(k)}: {int(in_both)} published, {row['in_top_k_both']} measured")
        assert abs(row["precision_at_k"] - precision) < 0.5e-3, (
            f"top-{int(k)}: precision {precision} published, {row['precision_at_k']} measured")


def test_the_slice_gate_spanning_counts_are_the_committed_query_output():
    fixture = FIXTURES / SLOTS["slice-gate"][1]
    if not fixture.is_file():
        pytest.skip("slice-gate: fixture absent, so the spanning counts are unchecked")
    spanning = json.loads(fixture.read_text())["spanning"]
    body = (ROOT / "results" / SLOTS["slice-gate"][2]).read_text().replace("\u202f", "").replace(" ", "")
    for column in ("txs_a", "txs_b", "in_addrs_a", "in_addrs_b", "reused_addrs_a"):
        assert str(spanning[column]) in body, (
            f"{column} is {spanning[column]} in the query output and appears nowhere in the document")
