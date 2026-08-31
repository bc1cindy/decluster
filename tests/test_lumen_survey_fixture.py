"""Pin the committed lumen fingerprint survey (`tests/fixtures/lumen_explorer_data.json`, 432 KB,
aggregate histograms only — no txid / address / value) that backs `results/RESULTS-fingerprint-
sparsity.md` and `results/RESULTS-attribute-drift.md` and the §5 fingerprint discussion in PAPER.md.
The survey is a whole-chain scan whose per-tx data cannot be re-run here; committing the aggregate
and pinning its documented metadata + internal consistency makes those survey-derived claims
reproducible from the repo rather than from an external run."""
import json
import os

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "lumen_explorer_data.json")


def _load():
    with open(FIX) as f:
        return json.load(f)


def test_survey_window_metadata_matches_results_docs():
    d = _load()
    assert d["window"]["epochs"] == 158                      # RESULTS: 158 epochs of 144 blocks
    assert d["window"]["start_height"] == 939969
    assert d["window"]["end_height"] == 962720
    assert d["totals"]["txs"] == 98_179_414                  # RESULTS-attribute-drift headline
    assert d["totals"]["defects"] == 0
    assert len(d["axis_summaries"]) == 21                    # RESULTS-attribute-drift: 21 axes


def test_every_axis_summary_is_a_normalised_distribution():
    for axis, s in _load()["axis_summaries"].items():
        shares = [v["share"] for v in s["values"]]
        assert abs(sum(shares) - 1.0) < 1e-9, axis
        assert s["distinct_values"] == len(s["values"]), axis
        assert s["largest_share"] == max(shares), axis
        assert s["smallest_share"] == min(shares), axis


def test_counts_are_consistent_with_the_total():
    d = _load()
    tot = d["totals"]["txs"]
    for axis, s in d["axis_summaries"].items():
        counts = sum(v["count"] for v in s["values"])
        assert counts == tot, f"{axis}: {counts} != {tot}"       # every tx classified on every axis
        for v in s["values"]:
            assert abs(v["share"] - v["count"] / tot) < 1e-9, (axis, v["value"])


def test_documented_dominant_shares():
    ax = _load()["axis_summaries"]
    assert ax["change_type"]["largest_value"] == "P2wpkh"
    assert round(ax["change_type"]["largest_share"], 3) == 0.635
    assert ax["change_position"]["largest_value"] == "First"
    assert round(ax["change_position"]["largest_share"], 3) == 0.561
