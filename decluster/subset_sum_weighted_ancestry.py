"""Opt-in ancestry walk weighted by subset-sum link evidence.

The shared solver remains in ``decluster.ancestry``; this namespace prevents the experimental
link-weighted walk from being mistaken for the nominal-value default.
"""

from .ancestry import (DEFAULT_LINK_BUDGET_MS, absorber_distribution, build_extended_graph,
                       dss_link_oracle)


def build_graph(target, depth=6, fetch=None, link_oracle=dss_link_oracle, value_weighted=False,
                subjective_oracle=None, max_nodes=None):
    return build_extended_graph(target, depth=depth, fetch=fetch, link_oracle=link_oracle,
                                value_weighted=value_weighted,
                                subjective_oracle=subjective_oracle, max_nodes=max_nodes)


__all__ = ["DEFAULT_LINK_BUDGET_MS", "absorber_distribution", "build_graph", "dss_link_oracle"]
