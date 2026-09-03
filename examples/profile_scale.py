"""Profile one clustering backend over a bounded prefix of a local epoch.

Use `/usr/bin/time -l` around this command to capture peak resident memory.

usage: python3 examples/profile_scale.py BACKEND MAX_TXS EPOCH.ndjson[.gz]
BACKEND is `dict` or `numpy`.
"""
import itertools
import json
import os
import resource
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.scale_cluster import (cluster_scale_np_stream, cluster_scale_stream,
                                     stream_txs)


def main(backend, max_txs, path):
    txs = itertools.islice(stream_txs([path]), max_txs)
    started = time.monotonic()
    if backend == "dict":
        clustering = cluster_scale_stream(txs)
    elif backend == "numpy":
        clustering = cluster_scale_np_stream(txs)
    else:
        raise SystemExit("BACKEND must be dict or numpy")
    print(json.dumps({"backend": backend, "max_txs": max_txs,
                      "clusters": clustering.n_clusters(),
                      "elapsed_seconds": round(time.monotonic() - started, 3),
                      "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
