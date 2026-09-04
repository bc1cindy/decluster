"""Close the intersection loop over a set of tracked coins.

Four channels in sequence, none of which decides on its own:

  monitor.walk_frontier      a co-spend of two tracked branches — the occasion
  ancestry.ancestry_signature each coin's candidate origins, walking backwards
  intersect.evaluate          the origins every branch shares
  intersect.score_candidate   cluster_refined's verdict on the co-spend itself

The last step is the one that matters. Co-spending is the common-input heuristic,
and the engine exists to refuse it where fingerprint and topology say to. Reporting
a narrowing without running that step asserts the heuristic under the attack's name.

Run it against the default seeds, or point it at any other set:

    ./.venv/bin/python -m examples.intersection_pipeline

An empty candidate list is the expected result until the owner consolidates, and
the run says so rather than printing nothing.
"""

from decluster.fetch import fetch_outspends, fetch_tx
from decluster.adaptations.intersection import evaluate_ancestry_reports
from decluster.intersect import evaluate, score_candidate
from decluster.monitor import summarise, walk_frontier

SIGNATURE_DEPTH = 3

# The seven 7.74840978 BTC outputs of the third mixing round, plus the spine's
# final change. Six entered separate mixes; two are still unspent.
ROUND3 = "80f11c778a2f486ffc55b4e8665a94971ae9c350ac53969e9efcbf90478cbf90"
SPINE_TAIL = "41846eaf5653706c4f040cca328f83b4ad52ab7cf3c159d7ebe0a6cf4b308508"
DENOMINATION = 774840978
TAIL_CHANGE = 13471


def default_seeds(get_tx=fetch_tx):
    """Outpoints worth watching: the attributed denomination plus the spine tail."""
    seeds = [
        (ROUND3, i)
        for i, o in enumerate(get_tx(ROUND3)["vout"])
        if o["value"] == DENOMINATION
    ]
    seeds += [
        (SPINE_TAIL, i)
        for i, o in enumerate(get_tx(SPINE_TAIL)["vout"])
        if o["value"] == TAIL_CHANGE
    ]
    return seeds


def default_signature_of(depth=SIGNATURE_DEPTH):
    """Each coin's candidate origins, from the backward absorbing walk.

    Shallower than `ancestry_signature`'s own default because a branch out of a
    mix has hundreds of parents per hop. It is a floor either way: the walk
    truncates at any transaction the link oracle refuses, which every large mix
    is, and reports that it did.

    The oracle is named, not inherited: the walk's default moved to nominal
    value flow, which never refuses, so inheriting it would drop both the
    truncation this floor rests on and the walk that RESULTS-intersection.md
    reports.
    """
    from decluster.ancestry import ancestry_signature_and_truncation, dss_link_oracle

    return lambda outpoint: ancestry_signature_and_truncation(
        outpoint, depth=depth, link_oracle=dss_link_oracle)


def default_ancestry_report_of(depth=SIGNATURE_DEPTH):
    """Atomic ancestry observation used by the typed intersection path."""
    from decluster.adaptations.ancestry import ancestry_signature_report
    from decluster.ancestry import dss_link_oracle

    return lambda outpoint: ancestry_signature_report(
        outpoint, depth=depth, link_oracle=dss_link_oracle
    )


def default_cluster_fn():
    """The engine, built on first use so a walk that finds nothing costs nothing.

    This is the step the module docstring calls the one that matters: the
    co-spend goes in as a prior, and fingerprint, amount and topology can still
    refuse it.
    """
    built = {}

    def cluster_fn(nodes, signatures=None):
        if "combiner" not in built:
            from decluster.combiner import Combiner

            built["combiner"] = Combiner.from_library()
        from decluster.cluster import cluster_refined

        return cluster_refined(
            nodes,
            built["combiner"],
            provenance=signatures is not None,
            signatures=signatures,
        )

    return cluster_fn


def run(seeds=None, get_tx=fetch_tx, get_outspends=fetch_outspends,
        signature_of=None, ancestry_report_of=None, cluster_fn=None, max_depth=3):
    """Walk, intersect, and score. Returns one dict per co-spend candidate.

    `ancestry_report_of` is the preferred interface: one typed result binds a
    signature to the truncation observed by the same walk. `signature_of` is the
    compatibility interface and returns `(signature, truncated)` for an outpoint — the origin set and, as an
    `ancestry.TruncationSupport`, how much of its boundary is truncation rather than an origin and
    which walk limit produced it. Both are needed: without the second, an empty intersection cannot
    be told from a walk that could not see, and without its split a blind branch does not say
    whether the oracle refused or the node cap bit. `cluster_fn` takes
    `(nodes, signatures)`. The functions are injected so the pipeline can be exercised without a
    network walk; production uses `default_ancestry_report_of()` and `default_cluster_fn()`.
    """
    if signature_of is not None and ancestry_report_of is not None:
        raise ValueError("provide signature_of or ancestry_report_of, not both")
    seeds = default_seeds(get_tx) if seeds is None else seeds
    walked = walk_frontier(seeds, get_tx, get_outspends, max_depth=max_depth)
    results = []
    for candidate in walked["candidates"]:
        entry = {"candidate": candidate}
        sigs = None
        if ancestry_report_of is not None:
            ancestry_reports = {
                op: ancestry_report_of(op) for op in candidate.get("outpoints", [])
            }
            sigs = {
                op: report.as_legacy()[0] for op, report in ancestry_reports.items()
            }
            entry["narrowing"] = evaluate_ancestry_reports(
                candidate, ancestry_reports.__getitem__
            ).as_legacy()
        elif signature_of is not None:
            # Computed once: the narrowing reads them, and the engine's
            # provenance channel is offered the same ones rather than a
            # second walk.
            walked_back = {op: signature_of(op) for op in candidate.get("outpoints", [])}
            sigs = {op: sig for op, (sig, _) in walked_back.items()}
            truncs = {op: t for op, (_, t) in walked_back.items()}
            entry["narrowing"] = evaluate(
                candidate, sigs.__getitem__, truncation_of=truncs.__getitem__
            )
        if cluster_fn is not None:
            entry["verdict"] = score_candidate(
                candidate, cluster_fn, lambda op: op[0], signatures=sigs
            )
        results.append(entry)
    return {"walk": walked, "results": results}


def main():
    out = run(
        ancestry_report_of=default_ancestry_report_of(),
        cluster_fn=default_cluster_fn(),
    )
    print(f"seeds: {len(default_seeds())}")
    print(f"walk: {summarise(out['walk'])}")
    for entry in out["walk"]["frontier"]:
        op = entry["outpoint"]
        print(f"   {entry['reason']:9s} d={entry['depth']}  {op[0][:16]}:{op[1]}")
    if not out["results"]:
        print()
        print("no co-spend candidate: every branch is still unspent or inside a mix.")
        print("the intersection has nothing to operate on until the owner consolidates.")
        return
    for entry in out["results"]:
        print(entry)


if __name__ == "__main__":
    main()
