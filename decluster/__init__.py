"""decluster: extractor -> distribution -> combiner -> clustering that refuses false merges.
Fingerprint surface: merged transaction/rust-merged transaction and #1676."""
from .fetch import fetch_tx
from .extractors import x_nsequence, x_input_order, x_io_shape, features
from .engine import measure, print_report, sample_recent_txs, locktime_class
from .combiner import Combiner
from .cluster import cluster_naive, cluster_fingerprint_aware
