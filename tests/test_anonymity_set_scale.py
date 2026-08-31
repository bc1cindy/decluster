"""Pin the committed §04 provenance-anonymity-set-at-scale snapshot (`results/scale_output.json`,
documented in `results/RESULTS-anonymity-set-scale.md`). The snapshot is a live-fetch run, so its
row values are not bit-reproducible; what IS reproducible and load-bearing is that the summary
block is *derivable from the rows* and the documented invariants hold. This turns a committed-but-
untested data file into a checked one."""
import json
import math
import os

SNAP = os.path.join(os.path.dirname(__file__), "..", "results", "scale_output.json")


def _load():
    with open(SNAP) as f:
        return json.load(f)


def test_summary_is_derivable_from_rows():
    d = _load()
    s, rows = d["summary"], d["rows"]
    # rows are the resolved subsample (>= 2 absorbers = real branching)
    assert len(rows) == s["resolved"]
    assert all(r["absorbers"] >= 2 for r in rows)
    assert s["resolve_rate"] == s["resolved"] / s["tried"]
    assert s["coverage_frac"] == s["coverage"] / s["resolved"]
    # mean graph entropy over the resolved rows reproduces the summary (the "covered" means are
    # over the coverage=3 subset, not derivable from the row fields, so they are not recomputed here)
    mean_graph = sum(r["graph_bits"] for r in rows) / len(rows)
    assert math.isclose(mean_graph, s["mean_graph_bits"], rel_tol=1e-9)
    # "sharpened" = rows where subjective fusion actually cut entropy (fused strictly below graph)
    assert sum(1 for r in rows if r["fused_bits"] < r["graph_bits"] - 1e-12) == s["sharpened"]


def test_fusion_never_increases_entropy():
    """The subjective readout is refuse-only on this axis: fused entropy never exceeds graph-only."""
    for r in _load()["rows"]:
        assert r["fused_bits"] <= r["graph_bits"] + 1e-12


def test_documented_headline_numbers():
    s = _load()["summary"]
    assert (s["tried"], s["resolved"]) == (30, 15)          # 50% resolved
    assert s["resolve_rate"] == 0.5
    assert round(s["mean_graph_bits"], 2) == 2.48           # doc: 2.48 bits
    assert round(s["mean_reduction_covered"], 2) == 0.30    # doc: 0.30 bits reduction on covered
