"""Offline partition-posterior harness on a bounded .cache slice. Reuses the ns-propagation
cache-run slice construction so it needs no network. Runs the sampler, reports the coarsening
hierarchy (fs_bayes pair-marginal vs M1 per-target vs this partition posterior), per-channel
marginal bits, a beta sweep by ECE, R-hat across chains, and a shuffle-null sanity check.
usage: .venv/bin/python -m examples.partition_posterior"""
import random
from decluster.partition_model import build_evidence, Evidence
from decluster.split_merge import run_chains
from decluster.partition_posterior import (
    coassignment, dahl_consensus, posterior_entropy, k_posterior, rhat, calibration)


def channel_ablation(supernodes, labels_same_owner, *, channels, seed=0):
    """Drop one channel at a time; report posterior entropy and calibration to size each
    channel's marginal contribution."""
    results = {}
    full = _run(supernodes, channels, seed)
    results["__all__"] = full
    for ch in channels:
        kept = [c for c in channels if c != ch]
        results[f"drop_{ch}"] = _run(supernodes, kept, seed)
    return results


def beta_sweep(supernodes, labels_same_owner, betas, seed=0):
    out = []
    for b in betas:
        ev = build_evidence(supernodes, beta=b)
        chains = run_chains(ev, inits=[list(range(ev.n))], n_iter=1500, burn=500, seed=seed)
        ca = coassignment(chains[0]["labels_samples"])
        out.append((b, calibration(ca, labels_same_owner)))
    return out


def _run(supernodes, channels, seed):
    beta = 1.0 if ("provenance" in channels or "topology" in channels) else 0.0
    link_fn = None if beta else (lambda a, b: 0.0)
    ev = build_evidence(supernodes, beta=beta, link_fn=link_fn)
    if "categorical" not in channels:               # blank the categorical axes
        ev = Evidence(n=ev.n, cat_vals=[[""] * len(ev.bases) for _ in range(ev.n)],
                      bases=ev.bases, conc=ev.conc, link=ev.link, cannot=ev.cannot, beta=ev.beta)
    chains = run_chains(ev, inits=[list(range(ev.n)), [0] * ev.n],
                        n_iter=2000, burn=600, seed=seed)
    s0 = chains[0]["labels_samples"]
    return {"entropy": posterior_entropy(s0), "k_post": k_posterior(s0),
            "consensus": dahl_consensus(s0),
            "rhat_K": rhat([[len(set(l)) for l in c["labels_samples"]] for c in chains])}


def _bounded_link_oracle(in_vals, out_vals, max_dim=24, budget_ms=250):
    """dss_link_oracle, but refuses (same semantics as any other oracle-None truncation in
    ancestry.build_extended_graph) on a tx whose subset-sum instance is too large to solve
    inside this offline harness's time budget -- a handful of cached txs are CoinJoin-scale
    (vin/vout in the hundreds) and the exact solver's own measured range is 54ms-69s per call
    (see ancestry.dss_link_oracle's docstring), which blows the harness runtime. Treating an
    oversized tx as a depth-boundary absorber is honest truncation, not fabrication."""
    from decluster.ancestry import dss_link_oracle
    if len(in_vals) > max_dim or len(out_vals) > max_dim:
        return None
    return dss_link_oracle(in_vals, out_vals, budget_ms=budget_ms)


def build_slice(cap_total=16, depth=3, max_supernodes=None):
    """Bounded real .cache slice -> (supernodes, labels_same_owner). Co-spend groups become
    supernodes (the atomic must-link unit the partition model assumes); address-reuse groups
    give the pairwise same-owner labels ACROSS supernodes -- the same anti-circularity split
    ns_propagation_cache_run.build_sample uses (co-spend seeds the state space, address-reuse
    seeds the label, two independent same-owner heuristics). `max_supernodes` truncates AFTER
    prioritizing labeled singles over unlabeled ones (deterministic), so a small slice still
    carries some same-owner label coverage for calibration -- pure sampling-budget curation,
    the underlying tx data is real and untouched."""
    from examples.ns_propagation_cache_run import load_cache_txs, build_sample, cache_fetch_tx
    from decluster.ancestry import build_extended_graph, absorber_distribution
    from decluster.propagate import entity_signature

    all_txs = load_cache_txs()
    nodes, cospend_groups, seed_labels, _children = build_sample(
        all_txs, cap_cospend_funders=cap_total, cap_total=cap_total)
    grouped = {txid for g in cospend_groups for txid in g}
    singles = [t for t in nodes if t not in grouped]
    labeled_singles = sorted(t for t in singles if t in seed_labels)
    unlabeled_singles = sorted(t for t in singles if t not in seed_labels)
    member_groups = (list(cospend_groups) + [[t] for t in labeled_singles]
                      + [[t] for t in unlabeled_singles])
    if max_supernodes is not None:
        member_groups = member_groups[:max_supernodes]

    supernodes, sn_labels = [], []
    for members in member_groups:
        txs = [all_txs[t] for t in members if t in all_txs]
        if not txs:
            continue
        sigs = []
        for t in members:
            if t not in all_txs:
                continue
            g = build_extended_graph((t, 0), depth=depth, fetch=cache_fetch_tx,
                                     link_oracle=_bounded_link_oracle)
            sigs.append(absorber_distribution(g, (t, 0)))
        supernodes.append({"txs": txs, "sig": entity_signature(sigs) if sigs else {}})
        sn_labels.append({seed_labels[t] for t in members if t in seed_labels})

    labels_same_owner = {}
    n = len(supernodes)
    for i in range(n):
        for j in range(i + 1, n):
            li, lj = sn_labels[i], sn_labels[j]
            if li and lj:                            # both sides carry an address-reuse label
                labels_same_owner[(i, j)] = 1 if (li & lj) else 0
    return supernodes, labels_same_owner


def fs_bayes_pair_marginal(supernodes, seed=0):
    """The pairwise (non-transitive) coarsening: fs_bayes' per-field Gibbs match posterior
    over the supernode representative txs, with no partition prior and no transitivity."""
    from itertools import combinations
    from decluster.fs_em import agree_matrix
    from decluster.fs_bayes import gibbs_fit
    from decluster.fingerprint_validate import LibraryScorer
    axes = LibraryScorer().axes
    reps = [sn["txs"][0] for sn in supernodes]
    idx_pairs = list(combinations(range(len(reps)), 2))
    tx_pairs = [(reps[i], reps[j]) for i, j in idx_pairs]
    A, mask, _names, u = agree_matrix(tx_pairs, axes)
    fit = gibbs_fit(A, mask, u, seed=seed)
    return {idx_pairs[k]: fit["p_match"][k] for k in range(len(idx_pairs))}


def shuffle_null(supernodes, seed=0):
    """Shuffle-null control (graph_deanon's shuffle_auc convention): decouple each channel's
    values from real supernode identity by independent random permutations, rerun the sampler,
    and compare posterior entropy to the real run. A real signal should show LOWER entropy
    (more structure) than the shuffled evidence; shuffled evidence should look close to the
    no-evidence prior."""
    ev = build_evidence(supernodes)
    real = run_chains(ev, inits=[list(range(ev.n))], n_iter=1500, burn=500, seed=seed)[0]

    rng = random.Random(seed)
    perm_cat = list(range(ev.n))
    rng.shuffle(perm_cat)
    shuffled_cat = [ev.cat_vals[perm_cat[i]] for i in range(ev.n)]
    perm_link = list(range(ev.n))
    rng.shuffle(perm_link)
    shuffled_link = {}
    for (i, j), w in ev.link.items():
        a, b = perm_link[i], perm_link[j]
        if a == b:
            continue
        key = (a, b) if a < b else (b, a)
        shuffled_link[key] = w
    ev_null = Evidence(n=ev.n, cat_vals=shuffled_cat, bases=ev.bases, conc=ev.conc,
                        link=shuffled_link, cannot=set(), beta=ev.beta)
    null = run_chains(ev_null, inits=[list(range(ev.n))], n_iter=1500, burn=500, seed=seed)[0]
    return {"real_entropy": posterior_entropy(real["labels_samples"]),
            "null_entropy": posterior_entropy(null["labels_samples"])}


if __name__ == "__main__":
    print("build a bounded slice via examples.ns_propagation_cache_run, then call the "
          "functions above; write results/RESULTS-partition-posterior.md from the output.")
