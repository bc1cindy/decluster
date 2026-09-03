"""Run the two Collection-A measurements on a real, committed-scale mainnet slice:

  1. Entity-level (epsilon,delta)-sparsity (Def 1). Cluster addresses (CIOH, refuse-guarded),
     contract the whole slice into a pseudonym graph, and measure the survival curve of each
     entity's nearest-neighbour cosine. A sparse space stays near zero until epsilon is high:
     the precondition Theorem 2 turns into de-anonymizability.

  2. Cross-view re-identification (the social-graph channel, cit 24). Split the slice into two
     epoch views, contract each, seed a fraction of the entities present in both, and let the
     structural/attribute matcher propagate. Precision/recall are reported *alongside* the
     graph_shape diagnostic of each view, so a weak match reads as "the contracted graph is not
     social enough here", not as an unexplained failure.

usage: python3 examples/analyze_slice_a.py slice_a_2016.ndjson [max_lines]
"""
import sys
import os
import json
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import views, def1_sparsity, graph_shape
from decluster.view_match import ViewMatcher


def load(path, cap=None):
    sample = []
    with open(path) as f:
        for line in f:
            if cap and len(sample) >= cap:
                break
            try:
                tx = json.loads(line)
            except Exception:
                continue
            sample.append((tx, int(tx.get("height", 0))))
    return sample


def _f(x, d=3):
    return f"{x:.{d}f}" if isinstance(x, (int, float)) else "n/a"


def shape_line(g, tag):
    s = graph_shape.summary(g)
    return (f"  [{tag}] V={s['vertices']} E={s['edges']} <k>={_f(s['mean_degree'],2)} "
            f"deg1={_f(s['degree_1_share'])} assort={_f(s['assortativity'])} "
            f"trans={_f(s['transitivity'],4)} cfg={_f(s['configuration_transitivity'],4)} "
            f"ratio={_f(s['transitivity_ratio'],2)} tail={_f(s['tail_exponent'],2)}")


def main(path, cap=None):
    print(f"loading {path}" + (f" (cap {cap})" if cap else ""), flush=True)
    sample = load(path, cap)
    print(f"  {len(sample)} txs", flush=True)

    print("clustering addresses (CIOH, refuse-guarded)...", flush=True)
    lookup = views.cluster_addresses(sample, refuse=True)
    print(f"  {len(set(lookup.values()))} clusters over {len(lookup)} addresses", flush=True)

    # ---- 1. entity-level (epsilon, delta)-sparsity ----
    print("\n== Def 1: entity-level sparsity ==", flush=True)
    g_full = views.contract(sample, lookup=lookup, axes=True)
    print(f"  contracted: {len(list(g_full.vertices))} vertices", flush=True)
    print(shape_line(g_full, "full"), flush=True)
    tops = def1_sparsity.nearest_similarities(g_full, query_n=2000, background_n=20000, min_degree=1, seed=0)
    surv = def1_sparsity.survival(tops)
    print(f"  nearest-neighbour survival delta(epsilon) over {len(tops)} entities:", flush=True)
    for e in sorted(surv):
        print(f"    epsilon={e:>4}: delta={surv[e]:.3f}", flush=True)

    # ---- 2. cross-view re-identification ----
    print("\n== Social graph: cross-view re-identification (epoch split) ==", flush=True)
    parts = views.partition_coins(sample, scheme="epoch")
    ga = views.contract(sample, indices=parts[0], lookup=lookup, axes=True)
    gb = views.contract(sample, indices=parts[1], lookup=lookup, axes=True)
    va, vb = set(ga.vertices), set(gb.vertices)
    overlap = sorted(va & vb)
    print(f"  view A={len(va)} vtx  view B={len(vb)} vtx  overlap={len(overlap)} entities", flush=True)
    print(shape_line(ga, "A"), flush=True)
    print(shape_line(gb, "B"), flush=True)
    if len(overlap) < 20:
        print("  overlap too small to matcher-evaluate", flush=True)
        return
    rng = random.Random(0)
    for seed_frac in (0.05, 0.10):
        seed_n = max(2, int(len(overlap) * seed_frac))
        seeds = set(rng.sample(overlap, seed_n))
        seed_map = {v: v for v in seeds}
        m = ViewMatcher().match(ga, gb, seed_map)
        guesses = {u: w for u, w in m.items() if u not in seeds}
        correct = sum(1 for u, w in guesses.items() if w == u)
        prec = correct / len(guesses) if guesses else 0.0
        rec = correct / (len(overlap) - len(seeds)) if len(overlap) > len(seeds) else 0.0
        print(f"  seed {seed_frac:.0%} ({seed_n}): guessed {len(guesses)}  correct {correct}  "
              f"precision {prec:.3f}  recall {rec:.3f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
