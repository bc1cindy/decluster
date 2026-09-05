"""decluster: fingerprint-aware probabilistic de-anonymization of Bitcoin transactions.

Two directions move through the partition refinement lattice, and which one a function travels is
part of its contract, not an implementation detail:

  `cluster_*`    ascends. Starts from the discrete partition and fuses blocks, so it owns every
                 merge it makes and keeps two owners apart by declining to merge them.
  `decluster_*`  descends. Takes a partition it did not build and cuts blocks the evidence says
                 hold more than one owner. It cannot decline a merge that already happened, so it
                 has to argue against one.

`Partition` carries both operations (`meet` descends, `join` ascends) and refuses to combine
partitions of different ground sets. `cluster.cluster_refined` predates the convention and
ascends despite its name; `declustering.decluster` is the descending pass.
"""
from .fetch import fetch_tx
from .extractors import x_nsequence, x_input_order, x_io_shape
from .engine import measure, print_report, sample_recent_txs, locktime_class
from .rarity_weight_baseline import Combiner
from .cluster import cluster_naive, cluster_refined
from .partition import Partition
from .conservation import forced_in_round
from .provenance import candidate_coins, rank_by_overlap
from .monitor import walk_frontier
from .intersect import evaluate, score_candidate
from .analyze import analyze, cluster_map, cluster_posterior
from .oracle import bounded_dss_link_oracle, bounded_link_oracle, subprocess_link_oracle
from .path_count import path_count_anonymity
from .provenance_route_accumulation import provenance_route_accumulation
