"""De-anonymization-driven link prediction against structure-only prediction, on planted views.

The corpus is synthetic and generated here, deterministically from each `--fixture-seeds`
value: a directed community graph is drawn once, each view keeps an independent random subset
of its edges, and a share of the target view's links is held out.  Nothing about it is a
Bitcoin measurement, and the numbers it produces are numbers about this fixture.  Real 2016
views behave very differently — see `results/RESULTS-ns-bitcoin.md`, where the same propagation
found zero usable independent seeds.

Five arms per fixture seed, all scored on identical held-out links:

  attack              seeds drawn from the withheld correspondence, real auxiliary view
  independent-aux     an auxiliary view drawn from its own graph, so the correspondence the
                      seeds assert is not a correspondence at all and every transferred edge
                      is noise
  deranged-seeds      the real auxiliary view, seeds pointing at the wrong vertices
  stripped-aux        the real auxiliary view with every held-out link deleted from it, which
                      leaves the mapping intact and removes only the evidence it transfers
  ceiling             the whole withheld correspondence as the seed set, which leaves
                      propagation nothing to do; a diagnostic, not an operating point

`--scorer open` ablates the closed-neighbourhood term from *both* arms, which is the sensitivity
the result turns on.

usage: python3 examples/link_prediction_run.py [--out PATH] [--manifest]
"""
import argparse
import json
import os
import random
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import reproducibility
from decluster.baselines import link_prediction as lp
from decluster.baselines.narayanan_shmatikov import evaluate
from decluster.ns_bitcoin import SEED_SAMPLED
from decluster.views import PseudonymGraph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_DOC = "RESULTS-link-prediction.md"
MANIFEST_SOURCE = "examples/link_prediction_run.py"

SEED_UNRELATED = "unrelated-auxiliary-control"
SEED_DERANGED = "deranged-correspondence-control"
SEED_STRIPPED = "withheld-correspondence-sample-on-a-stripped-auxiliary"
SEED_CEILING = "withheld-correspondence-as-the-mapping"

SCORERS = {"closed": lp.score, "open": lp.open_score}


def directed_graph(vertices, edges):
    graph = PseudonymGraph(axes=False)
    for vertex in vertices:
        graph._vertex(vertex)
    for source, target in edges:
        graph.edges[(source, target)] = {"transfers": 1, "value": 1}
        graph._out[source].add(target)
        graph._in[target].add(source)
    return graph


def community_edges(vertices, groups, p_in, p_out, rng):
    """A planted-partition digraph: dense inside a group, sparse across.

    Communities are the point of the fixture, not decoration.  On a graph with no community
    structure a common-neighbour predictor has nothing to find, and the structure-only arm
    would lose to anything at all; giving it real signal is what makes the comparison worth
    running.
    """
    size = vertices // groups
    return [(u, v) for u in range(vertices) for v in range(vertices)
            if u != v and rng.random() < (p_in if u // size == v // size else p_out)]


def planted_views(args, rng):
    """Two partial views of one activity graph, plus what was withheld from the target."""
    edges = community_edges(args.vertices, args.groups, args.p_in, args.p_out, rng)
    target_edges = [e for e in edges if rng.random() < args.keep]
    auxiliary_edges = [e for e in edges if rng.random() < args.keep]

    # Hold out whole links, both directions: leaving the reverse edge in place would make a
    # "held-out" pair one the target view still joins, and the structure-only arm would be
    # scored on a pair it can read off its own input.
    links = sorted({tuple(sorted(e)) for e in target_edges})
    held = set(rng.sample(links, round(len(links) * args.holdout)))
    residual = [e for e in target_edges if tuple(sorted(e)) not in held]

    target = directed_graph([f"a{i}" for i in range(args.vertices)],
                            [(f"a{u}", f"a{v}") for u, v in residual])
    auxiliary = directed_graph([f"b{i}" for i in range(args.vertices)],
                               [(f"b{u}", f"b{v}") for u, v in auxiliary_edges])
    correspondence = {f"a{i}": f"b{i}" for i in range(args.vertices)}
    held_out = [(f"a{u}", f"a{v}") for u, v in sorted(held)]
    negatives = sample_negatives(args, links, held, rng)
    return {
        "target": target, "auxiliary": auxiliary, "correspondence": correspondence,
        "held_out": held_out, "negatives": negatives,
        "activity_edges": len(edges), "target_edges": len(target_edges),
        "auxiliary_edges": len(auxiliary_edges), "residual_edges": len(residual),
        "held_out_links_in_auxiliary": sum(
            1 for link in held if link in {tuple(sorted(e)) for e in auxiliary_edges}),
    }


def sample_negatives(args, links, held, rng):
    """Pairs the activity graph never joined, at `--negatives-per-positive` of the held-out set.

    Uniform over vertex pairs, so the negatives are mostly cross-community.  That is a property
    of the fixture worth stating rather than tuning away: a negative set drawn inside the
    communities would be harder for both arms.
    """
    joined = set(links)
    negatives, seen = [], set()
    while len(negatives) < args.negatives_per_positive * len(held):
        pair = tuple(sorted((rng.randrange(args.vertices), rng.randrange(args.vertices))))
        if pair[0] == pair[1] or pair in joined or pair in seen:
            continue
        seen.add(pair)
        negatives.append((f"a{pair[0]}", f"a{pair[1]}"))
    return negatives


def sampled_seeds(correspondence, fraction, rng):
    keys = sorted(correspondence)
    return {u: correspondence[u] for u in rng.sample(keys, round(len(keys) * fraction))}


def deranged(seeds, rng):
    """The same seed vertices with the wrong images; redrawn until nothing is left in place."""
    images = list(seeds.values())
    for _ in range(64):
        rng.shuffle(images)
        candidate = dict(zip(seeds, images))
        if all(candidate[u] != v for u, v in seeds.items()):
            return candidate
    return dict(zip(seeds, images))


def without_links(graph, links, correspondence):
    """The auxiliary view with the target's held-out links deleted, both directions.

    The mapping propagation finds is left to move as it will — an auxiliary view that never saw
    those links is a coherent counterfactual view, not the same view with a hole punched in the
    scoring — and what is removed is exactly the evidence the transfer would carry.
    """
    banned = {frozenset((correspondence[u], correspondence[v])) for u, v in links}
    return directed_graph(graph.vertices,
                          [e for e in graph.edges if frozenset(e) not in banned])


def unrelated_auxiliary(args, rng):
    """An auxiliary view of a different activity graph, under the same vertex names."""
    return directed_graph([f"b{i}" for i in range(args.vertices)],
                          [(f"b{u}", f"b{v}") for u, v in
                           community_edges(args.vertices, args.groups, args.p_in, args.p_out, rng)])


def _row(name, provenance, result, mapping_quality=None):
    row = {"arm": name, **asdict(result)}
    if mapping_quality is not None:
        row["mapping_against_withheld_correspondence"] = mapping_quality
    row["seed_provenance"] = provenance
    return row


def run_fixture(args, fixture_seed):
    rng = random.Random(fixture_seed)
    views = planted_views(args, rng)
    target, auxiliary = views["target"], views["auxiliary"]
    correspondence = views["correspondence"]
    held_out, negatives = views["held_out"], views["negatives"]
    seeds = sampled_seeds(correspondence, args.seed_fraction, rng)

    scorer = SCORERS[args.scorer]

    def compare(aux, seed_map, provenance):
        return lp.compare(target, aux, seed_map, held_out, negatives,
                          seed_provenance=provenance, theta=args.theta, cutoff=args.cutoff,
                          scorer=scorer)

    attack = compare(auxiliary, seeds, SEED_SAMPLED)
    mapping = lp.predict(target, auxiliary, seeds, held_out,
                         seed_provenance=SEED_SAMPLED, theta=args.theta).mapping
    quality = evaluate(mapping, correspondence, seeds)
    # How much of the arm's reach is the auxiliary view simply handing over the missing link,
    # rather than the enlarged neighbourhoods implying it.
    enlarged, _ = lp.transferred_neighbourhoods(target, auxiliary, mapping)
    direct = sum(1 for u, v in held_out if v in enlarged.get(u, ()))

    control_rng = random.Random(fixture_seed + 1000)
    unrelated = compare(unrelated_auxiliary(args, control_rng), seeds, SEED_UNRELATED)
    scrambled = compare(auxiliary, deranged(seeds, control_rng), SEED_DERANGED)
    stripped = compare(without_links(auxiliary, held_out, correspondence), seeds, SEED_STRIPPED)
    # Seeding with the whole correspondence leaves propagation nothing to do, so this row is the
    # transfer's ceiling under a perfect mapping.  It is a diagnostic and not an operating point:
    # the correspondence is withheld, and no attacker can seed with it.
    ceiling = compare(auxiliary, correspondence, SEED_CEILING)

    return {
        "fixture_seed": fixture_seed,
        "views": {k: v for k, v in views.items()
                  if k not in ("target", "auxiliary", "correspondence", "held_out", "negatives")},
        "held_out_links": len(held_out), "negative_pairs": len(negatives),
        "held_out_links_transferred_directly": direct,
        "runs": [_row("attack", SEED_SAMPLED, attack, quality),
                 _row("independent-auxiliary-control", SEED_UNRELATED, unrelated),
                 _row("deranged-seed-control", SEED_DERANGED, scrambled),
                 _row("stripped-auxiliary-control", SEED_STRIPPED, stripped),
                 _row("perfect-mapping-ceiling", SEED_CEILING, ceiling)],
    }


def manifest_invariants(report):
    """The population and headline facts a byte digest of the generator cannot see."""
    config = report["configuration"]
    attacks = [f["runs"][0] for f in report["fixtures"]]
    return {
        **config,
        "fixtures": len(report["fixtures"]),
        "held_out_links": [f["held_out_links"] for f in report["fixtures"]],
        "auc_deanonymization": [round(a["deanonymization"]["auc"], 6) for a in attacks],
        "auc_structure_only": [round(a["structure_only"]["auc"], 6) for a in attacks],
        "recall_deanonymization": [round(a["deanonymization"]["recall"], 6) for a in attacks],
        "recall_structure_only": [round(a["structure_only"]["recall"], 6) for a in attacks],
        "beats_structure_only": [a["separability"]["beats_structure_only"] for a in attacks],
        "held_out_links_transferred_directly": [f["held_out_links_transferred_directly"]
                                                for f in report["fixtures"]],
        "control_verdicts": sorted({run["separability"]["beats_structure_only"]
                                    for f in report["fixtures"] for run in f["runs"]
                                    if run["arm"].endswith("-control")}, key=repr),
    }


def configuration(args):
    return {"vertices": args.vertices, "groups": args.groups, "p_in": args.p_in,
            "p_out": args.p_out, "keep": args.keep, "holdout": args.holdout,
            "negatives_per_positive": args.negatives_per_positive,
            "seed_fraction": args.seed_fraction, "theta": args.theta, "cutoff": args.cutoff,
            "scorer": args.scorer, "fixture_seeds": list(args.fixture_seeds)}


def build_report(args):
    return {"configuration": configuration(args),
            "fixtures": [run_fixture(args, seed) for seed in args.fixture_seeds]}


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertices", type=int, default=80)
    parser.add_argument("--groups", type=int, default=8)
    parser.add_argument("--p-in", type=float, default=0.18)
    parser.add_argument("--p-out", type=float, default=0.012)
    parser.add_argument("--keep", type=float, default=0.9,
                        help="probability a view observes any one activity edge")
    parser.add_argument("--holdout", type=float, default=0.25,
                        help="share of the target view's links removed and predicted")
    parser.add_argument("--negatives-per-positive", type=int, default=4)
    parser.add_argument("--seed-fraction", type=float, default=0.25,
                        help="seeds drawn from the withheld correspondence")
    parser.add_argument("--theta", type=float, default=1.5)
    parser.add_argument("--cutoff", type=int, default=2,
                        help="score at which a candidate is declared a link")
    parser.add_argument("--scorer", choices=sorted(SCORERS), default="closed",
                        help="'open' ablates the closed-neighbourhood term from both arms")
    parser.add_argument("--fixture-seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument("--out", default=None)
    parser.add_argument("--manifest", nargs="?", const=MANIFEST_DOC, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    report = build_report(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out:
        with open(os.path.join(ROOT, args.out), "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
    if args.manifest:
        reproducibility.write_manifest(args.manifest, MANIFEST_SOURCE,
                                       manifest_invariants(report), root=ROOT)
        sys.stderr.write(f"wrote {reproducibility.manifest_path(args.manifest, ROOT)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
