# Path-count implementation contract

Generated from the canonical experiment artifact. Do not edit manually.

The ancestry and path-count distributions are identical on the fixed two-hop DAG: `{'origin-a:0': 0.62, 'origin-b:0': 0.38}`.

The resulting min-entropy is 0.689660 bits and Shannon entropy is 0.958042 bits. Changing the supplied count oracle from log W = 0 to log W = ln(100) leaves the distribution unchanged: `True`.

Route accumulation is implemented: `True`. Edge-disjoint path enumeration, plausible-flow capacity and k-routes are implemented: `True`, `False`, `True`.

This is a provenance-route diagnostic, not CTP robust connectivity or CoinScore.
