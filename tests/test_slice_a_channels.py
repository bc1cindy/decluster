"""Pin what Collection A settles about the *entity-attribute* and *social-graph* channels, on a
committed real slice (2016 mainnet blocks 400000-400005, addresses only, from `bigquery/graph.sql`,
frozen at `tests/fixtures/slice_a_channels_2016.ndjson.gz`).

The load-bearing, reproducible finding is a NEGATIVE that sharpens the thesis: the entity-attribute
feature space is *dense*, not (epsilon,delta)-sparse. Almost every entity has a near-twin even at
epsilon=0.9, so the Netflix sparse-record precondition (Def 1 / Theorem 2) does NOT hold on this
channel. The de-anonymizing sparsity lives in the *ancestry* channel (see `test_reid.py`,
`RESULTS-reid.md`), not here. The contracted graph is also disassortative (a transactional, not a
social, network), the structural reason the cross-view matcher stays underpowered.

Only the two SLICE-STABLE facts are pinned: the density curve and the sign of assortativity. The
cross-view match precision and the transitivity ratio are strongly scale-dependent (measured
transitivity_ratio ~7 on 6 blocks, ~0 on 150k txs), so they are reported in
`results/RESULTS-slice-a-channels.md` from the full-slice run rather than band-pinned here."""
import gzip
import json
import os

from decluster import views, def1_sparsity, graph_shape

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "slice_a_channels_2016.ndjson.gz")


def _sample():
    with gzip.open(FIX, "rt") as f:
        return [(json.loads(l), 0) for l in f]


def _contracted(sample):
    lookup = views.cluster_addresses(sample, refuse=True)
    return lookup, views.contract(sample, lookup=lookup, axes=True)


def test_entity_attribute_space_is_dense_not_sparse():
    """Def 1 measured on entity attribute vectors: the survival curve stays high, so the space is
    dense. This is the opposite of the ancestry channel and is why the attribute channel does not
    de-anonymize by itself."""
    sample = _sample()
    assert len(sample) > 5000
    lookup, g = _contracted(sample)
    assert len(set(lookup.values())) > 1000           # clustering actually ran
    tops = def1_sparsity.nearest_similarities(g, query_n=1200, background_n=12000, min_degree=2, seed=0)
    surv = def1_sparsity.survival(tops, epsilons=(0.5, 0.9, 0.99))
    assert surv[0.5] >= 0.99                            # doc 1.000
    assert surv[0.9] >= 0.95                            # doc 1.000 — dense: near-twin at eps 0.9
    assert surv[0.99] >= 0.90                           # doc 0.990

    # Not an artefact of the one-transaction clusters that dominate the population: the
    # density holds, weakening only mildly, when the query set is restricted to the hubs.
    hubs = def1_sparsity.nearest_similarities(g, query_n=1200, background_n=12000,
                                              min_degree=20, seed=0)
    assert def1_sparsity.survival(hubs, epsilons=(0.9,))[0.9] >= 0.85   # doc 0.921


def test_contracted_graph_is_disassortative_not_social():
    """The stable structural fact behind the underpowered cross-view match: the pseudonym graph is
    disassortative (hubs attach to leaves), a transactional rather than a social network."""
    _, g = _contracted(_sample())
    s = graph_shape.summary(g)
    assert s["assortativity"] < 0                       # doc -0.044; social graphs are positive
