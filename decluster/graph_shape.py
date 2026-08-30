"""Is the contracted pseudonym graph a social network in the sense the matching needs?

The framework asserts it is: the cluster graph under an incomplete clustering "is a social
network per Shmatikov and Narayanan's definition". Everything downstream rests on that, and
it is an assertion rather than a measurement. The algorithms were validated on social
graphs, which are heavy-tailed, strongly clustered, and assortative — a vertex sits in a
tight neighbourhood of vertices that are themselves well connected, which is what lets its
neighbours identify it.

Each statistic is reported against a configuration-model null with the same degree sequence,
because the raw value alone says little: a graph can look clustered simply by being dense.
The null answers "more than the degrees alone would produce?", which is the question.

Offline, stdlib only.
"""
import math
import random


def degrees(g):
    return {v: g.degree(v) for v in g.vertices}


def moments(deg):
    """(<k>, <k^2>) over the degree sequence."""
    n = len(deg)
    if not n:
        return 0.0, 0.0
    k1 = sum(deg.values()) / n
    k2 = sum(d * d for d in deg.values()) / n
    return k1, k2


def assortativity(g):
    """Pearson correlation of the degrees at the two ends of an edge. Social graphs come out
    positive: well-connected people know well-connected people. Technological and
    transactional graphs come out negative, hubs attaching to leaves."""
    xs, ys = [], []
    for u in g.vertices:
        for v in g.neighbours(u):
            xs.append(g.degree(u))
            ys.append(g.degree(v))          # each undirected edge is seen from both ends
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den if den else None


def transitivity(g, sample=None, rng=None):
    """Global clustering: closed triples over all triples. Sampling vertices bounds the cost
    on a large graph; the estimate is over the sampled vertices' triples."""
    verts = list(g.vertices)
    if sample and sample < len(verts):
        verts = (rng or random.Random(0)).sample(verts, sample)
    triples = closed = 0
    for u in verts:
        nb = g.neighbours(u)
        d = len(nb)
        if d < 2:
            continue
        triples += d * (d - 1) // 2
        nb_list = list(nb)
        for i in range(len(nb_list)):
            ni = g.neighbours(nb_list[i])
            for j in range(i + 1, len(nb_list)):
                if nb_list[j] in ni:
                    closed += 1
    return closed / triples if triples else None


def configuration_transitivity(deg):
    """Clustering a random graph with this exact degree sequence would show. The standard
    configuration-model expectation, ((<k^2> - <k>)^2) / (<k>^3 n). Anything a real graph
    has above this is structure the degrees do not explain."""
    n = len(deg)
    k1, k2 = moments(deg)
    if not n or k1 <= 0:
        return None
    return ((k2 - k1) ** 2) / (k1 ** 3 * n)


def tail_exponent(deg, kmin=2):
    """Hill estimator of the power-law exponent above kmin. Social graphs sit near 2 to 3;
    a much steeper tail means the hubs a heavy-tailed graph relies on are not there."""
    xs = [d for d in deg.values() if d >= kmin]
    if len(xs) < 2:
        return None
    s = sum(math.log(x / kmin) for x in xs)
    return 1 + len(xs) / s if s else None


def summary(g, sample=20000, rng=None):
    deg = degrees(g)
    k1, k2 = moments(deg)
    obs = transitivity(g, sample, rng)
    null = configuration_transitivity(deg)
    return {
        "vertices": len(deg),
        "edges": len(g.edges),
        "mean_degree": k1,
        "second_moment": k2,
        "degree_1_share": sum(1 for d in deg.values() if d <= 1) / max(len(deg), 1),
        "transitivity": obs,
        "configuration_transitivity": null,
        "transitivity_ratio": (obs / null) if obs and null else None,
        "assortativity": assortativity(g),
        "tail_exponent": tail_exponent(deg),
    }
