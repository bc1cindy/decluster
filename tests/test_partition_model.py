import math
from decluster.partition_model import Evidence, categorical_loglik, cluster_loglik, groups, log_posterior


def _ev(cat_vals, bases, conc=1.0):
    return Evidence(n=len(cat_vals), cat_vals=cat_vals, bases=bases, conc=conc,
                    link={}, cannot=set(), beta=1.0)


def _ev_full(cat_vals, bases, link, cannot, conc=1.0, beta=1.0):
    return Evidence(n=len(cat_vals), cat_vals=cat_vals, bases=bases, conc=conc,
                    link=link, cannot=cannot, beta=beta)


def test_agreement_beats_disagreement_single_axis():
    base = {"A": 0.5, "B": 0.5}
    ev = _ev([["A"], ["A"], ["B"]], [base], conc=1.0)
    agree = categorical_loglik([0, 1], ev)      # both "A"
    disagree = categorical_loglik([0, 2], ev)   # "A" vs "B"
    assert agree > disagree


def test_rarer_shared_value_scores_higher():
    # Rarity evidence lives in the merge gain (like fs_bayes's m/u ratio), not the raw
    # pair likelihood. base = population share: rare value -> small share.
    ev = _ev([["rare"], ["rare"], ["common"], ["common"]],
             [{"rare": 0.05, "common": 0.95}], conc=1.0)
    def gain(pair):
        i, j = pair
        return (categorical_loglik([i, j], ev)
                - categorical_loglik([i], ev) - categorical_loglik([j], ev))
    assert gain((0, 1)) > gain((2, 3))   # sharing a rare value is stronger merge evidence


def test_matches_hand_computed_dirichlet_multinomial():
    base = {"A": 0.5, "B": 0.5}
    ev = _ev([["A"], ["A"]], [base], conc=2.0)  # gamma_A = gamma_B = 1.0
    # DirMult: lgamma(2) - lgamma(4) + [lgamma(2+1)-lgamma(1)]  (both members "A")
    want = math.lgamma(2.0) - math.lgamma(4.0) + (math.lgamma(3.0) - math.lgamma(1.0))
    assert abs(categorical_loglik([0, 1], ev) - want) < 1e-9


def test_ns_link_adds_cohesion():
    base = {"A": 1.0}
    ev = _ev_full([["A"], ["A"]], [base], link={(0, 1): 2.0}, cannot=set(), beta=0.5)
    with_link = cluster_loglik([0, 1], ev)
    ev0 = _ev_full([["A"], ["A"]], [base], link={}, cannot=set(), beta=0.5)
    assert abs((with_link - cluster_loglik([0, 1], ev0)) - 0.5 * 2.0) < 1e-9


def test_cannot_link_forbids_merge():
    base = {"A": 1.0}
    ev = _ev_full([["A"], ["A"]], [base], link={}, cannot={frozenset({0, 1})})
    assert log_posterior([0, 0], ev) == -math.inf      # merged -> forbidden
    assert log_posterior([0, 1], ev) > -math.inf       # split -> allowed


def test_log_posterior_sums_clusters_plus_prior():
    from decluster.partition_prior import log_prior
    base = {"A": 0.5, "B": 0.5}
    ev = _ev_full([["A"], ["A"], ["B"]], [base], link={}, cannot=set(), conc=2.0)
    labels = [0, 0, 1]
    want = (cluster_loglik([0, 1], ev) + cluster_loglik([2], ev)
            + log_prior([2, 1], kind="microcluster"))
    assert abs(log_posterior(labels, ev) - want) < 1e-9


from decluster.partition_model import build_evidence, contract_cospend


def test_contract_cospend_groups_shared_input_addresses():
    txs = [
        {"vin": [{"prevout": {"scriptpubkey_address": "a"}}]},
        {"vin": [{"prevout": {"scriptpubkey_address": "a"}}]},  # shares 'a' -> same group
        {"vin": [{"prevout": {"scriptpubkey_address": "b"}}]},
    ]
    gs = contract_cospend(txs)
    sizes = sorted(len(g) for g in gs)
    assert sizes == [1, 2]


def test_build_evidence_populates_axes_and_links():
    sn = [
        {"txs": [{"vin": [{"prevout": {"scriptpubkey_address": "a"}}],
                  "vout": [{"scriptpubkey_address": "x"}]}], "sig": {"o1": 1.0}},
        {"txs": [{"vin": [{"prevout": {"scriptpubkey_address": "b"}}],
                  "vout": [{"scriptpubkey_address": "y"}]}], "sig": {"o1": 1.0}},
    ]
    ev = build_evidence(sn, beta=1.0)
    assert ev.n == 2
    assert len(ev.bases) == len(ev.cat_vals[0])          # one base per axis
    assert ev.link.get((0, 1), 0.0) > 0.0                # shared ancestor o1 -> positive link


def test_unmeasured_axis_value_gives_no_merge_boost():
    base = {"A": 0.5, "B": 0.5}
    # both members carry a value NOT in base on the single axis -> must abstain (no evidence)
    ev = _ev([["Z"], ["Z"]], [base], conc=1.0)
    gain = (categorical_loglik([0, 1], ev)
            - categorical_loglik([0], ev) - categorical_loglik([1], ev))
    assert abs(gain) < 1e-12
