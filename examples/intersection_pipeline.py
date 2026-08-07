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
    """
    from decluster.ancestry import ancestry_signature_and_truncation

    return lambda outpoint: ancestry_signature_and_truncation(outpoint, depth=depth)


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
        signature_of=None, cluster_fn=None, max_depth=3):
    """Walk, intersect, and score. Returns one dict per co-spend candidate.

    `signature_of` returns `(signature, truncated)` for an outpoint — the origin set and how much of
    its boundary is the link oracle refusing rather than an origin. Both are needed: without the
    second, an empty intersection cannot be told from a walk that could not see. `cluster_fn` takes
    `(nodes, signatures)`. Both are injected so the pipeline can be exercised without a network walk;
    production passes `default_signature_of()` and `default_cluster_fn()`.
    """
    seeds = default_seeds(get_tx) if seeds is None else seeds
    walked = walk_frontier(seeds, get_tx, get_outspends, max_depth=max_depth)
    results = []
    for candidate in walked["candidates"]:
        entry = {"candidate": candidate}
        sigs = None
        if signature_of is not None:
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
    out = run(signature_of=default_signature_of(), cluster_fn=default_cluster_fn())
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
