"""Netflix-faithful definitive reid on a UNIFORM ancestry sample (from collect_ancestry.py).
Reports, per Narayanan-Shmatikov: the (epsilon,delta)-sparsity survival curve (App E / Fig 12),
Algorithm 1B de-anonymization rate as a function of aux size m (Fig 1), stratified by the coins'
own sparsity, and the not-in-sample false-positive control (Fig 2: remove the target, expect abstain).

usage: python3 examples/reid_definitive.py <anc_uniform.ndjson>
"""
import sys
import os
import json
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.reid import reid_attack, top_similarity
from decluster.propagate import build_rarity
from decluster.def1_sparsity import survival
from decluster.ancestry import provenance_link


def load(path):
    coins, sigs = [], {}
    for line in open(path):
        d = json.loads(line)
        coins.append(d["coin"]); sigs[d["coin"]] = {a: float(m) for a, m in d["sig"].items()}
    return coins, sigs


def not_in_sample_control(coins, sigs, rarity, m=8, trials=200, seed=0):
    """Fig 2: reveal a target's aux but REMOVE it from the candidate set; a faithful attack should
    ABSTAIN (no confident match) rather than mis-attribute. Returns the abstain rate."""
    rng = random.Random(seed)
    from decluster.propagate import eccentricity
    abst = tot = 0
    pool = [c for c in coins if len(sigs[c]) >= m]
    for c in rng.sample(pool, min(trials, len(pool))):
        aux = {a: sigs[c][a] for a in rng.sample(list(sigs[c]), m)}
        others = [x for x in coins if x != c]
        scores = [provenance_link(aux, sigs[x], rarity) for x in others]
        if len(scores) < 2:
            continue
        tot += 1
        if eccentricity(scores) < 1.5:   # gate abstains -> correct (target absent)
            abst += 1
    return abst / tot if tot else None


def main(path):
    coins, sigs = load(path)
    rarity = build_rarity(sigs.values())
    print(f"N={len(coins)} coins | median dims={sorted(len(s) for s in sigs.values())[len(sigs)//2]}", flush=True)

    tops = list(top_similarity(coins, sigs).values())
    print("\n(epsilon,delta)-sparsity survival (fraction with a neighbour > epsilon):")
    for eps, frac in survival(tops).items():
        print(f"  epsilon={eps}: delta={frac:.3f}")

    sparse = [c for c in coins if _top(c, coins, sigs) < 0.5]
    dense = [c for c in coins if _top(c, coins, sigs) >= 0.9]
    print(f"\nstrata: sparse(top<0.5)={len(sparse)} dense(top>=0.9)={len(dense)}")
    print("\nAlgorithm 1B de-anon rate vs aux size m (exact-hit / attackable):")
    print(f"{'m':>3}{'sparse':>10}{'dense':>10}")
    for m in (2, 4, 6, 8):
        ds, es, ts = reid_attack(sparse, coins, sigs, rarity, m)
        dd, ed, td = reid_attack(dense, coins, sigs, rarity, m)
        print(f"{m:>3}{(es/ts if ts else 0):>10.3f}{(ed/td if td else 0):>10.3f}", flush=True)

    ctrl = not_in_sample_control(coins, sigs, rarity)
    print(f"\nnot-in-sample control (abstain rate, want high): {ctrl:.3f}" if ctrl else "\nnot-in-sample control: n/a")


_TOPCACHE = {}
def _top(c, coins, sigs):
    if not _TOPCACHE:
        _TOPCACHE.update(top_similarity(coins, sigs))
    return _TOPCACHE[c]


if __name__ == "__main__":
    main(sys.argv[1])
