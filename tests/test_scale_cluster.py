"""The dense-integer (numpy) union-find must produce the identical partition to the dict-based
streaming clustering; it is only a more compact representation."""
import json
import os
import tempfile
import gzip
from collections import defaultdict

from decluster.scale_cluster import cluster_scale, cluster_scale_np


def _tx(ins, outs):
    return {"vin": [{"prevout": {"scriptpubkey_address": a}} for a in ins],
            "vout": [{"scriptpubkey_address": a} for a in outs]}


def _write(rows):
    fd, path = tempfile.mkstemp(suffix=".ndjson")
    with os.fdopen(fd, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _partition(cl, addrs):
    g = defaultdict(set)
    for a in addrs:
        g[cl.get(a, a)].add(a)
    return {frozenset(v) for v in g.values() if len(v) >= 2}


def test_np_union_find_reproduces_the_dict_partition():
    rows = [_tx(["a1", "a2"], ["a3"]), _tx(["a2", "a4"], ["x"]),   # cluster {a1,a2,a4}
            _tx(["b1", "b2"], ["y"]),                               # cluster {b1,b2}
            _tx(["c1"], ["z"]),                                     # singleton (single input)
            _tx([f"m{i}" for i in range(20)], [f"o{i}" for i in range(20)])]  # coinjoin -> skipped
    addrs = {"a1", "a2", "a4", "b1", "b2", "c1"}
    path = _write(rows)
    try:
        p_dict = _partition(cluster_scale([path]), addrs)
        p_np = _partition(cluster_scale_np([path]), addrs)
        assert p_dict == p_np
        assert frozenset({"a1", "a2", "a4"}) in p_np and frozenset({"b1", "b2"}) in p_np
    finally:
        os.remove(path)


def test_np_union_find_reads_gzip_directly():
    rows = [_tx(["a", "b"], ["x"]), _tx(["b", "c"], ["y"])]
    fd, path = tempfile.mkstemp(suffix=".ndjson.gz")
    os.close(fd)
    try:
        with gzip.open(path, "wt") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")
        got = cluster_scale_np([path])
        assert got.get("a") == got.get("b") == got.get("c")
        mapped = got.map_many(["a", "b", "c", "singleton"])
        assert mapped["a"] == mapped["b"] == mapped["c"]
        assert mapped["singleton"] == "singleton"
    finally:
        os.remove(path)


def test_the_scalable_clusterer_refuses_the_same_shapes_as_the_reference_detector():
    """`cluster_scale*` duplicated the many-in/many-out rule inline, so it could not see the
    equal-amount coinjoin the reference detector was taught to catch. One detector, both paths."""
    from decluster.monitor import is_coinjoin
    from decluster.scale_cluster import cluster_scale_stream, cluster_scale_np_stream

    def mix(ins, denom, n_equal):
        return {"vin": [{"prevout": {"scriptpubkey_address": a, "value": 6_000_000}} for a in ins],
                "vout": [{"scriptpubkey_address": f"o{i}", "value": denom} for i in range(n_equal)]}

    whirlpool = mix(["w1", "w2", "w3", "w4", "w5"], 5_000_000, 5)
    assert is_coinjoin(whirlpool)                       # equal denomination, five participants
    for backend in (cluster_scale_stream, cluster_scale_np_stream):
        c = backend([whirlpool])
        assert c.get("w1", "w1") != c.get("w2", "w2")   # refused: no common-input merge
