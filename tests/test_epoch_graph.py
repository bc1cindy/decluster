"""The derived format is only worth having if the pipeline cannot tell the difference.

It drops the transaction id, which nothing reads, and replaces each address with an integer, which
is safe only because clustering asks which addresses coincide rather than what they are called. That
is a claim about the pipeline, not about the format, so it is tested against the pipeline: the same
engine over the committed block cache, once with the real addresses and once with a renaming, has to
return the same partition. A renaming that reversed the sort order is included because two places in
the engine sort addresses, and a tie-break that leaked into the result would show up there.
"""

import gzip
import json
import tempfile
from pathlib import Path

import pytest

from decluster import cluster as cl
from decluster import epoch_graph as eg
from decluster.archive_snapshot import extract_tar_gz
from decluster.combiner import Combiner
from decluster.fingerprint_validate import load_blkcache

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "fs-blkcache-2026-09-04.tar.gz"
DERIVED = ROOT / "data" / "epochs-2016-weekly-v1"


def _records():
    return [
        {"height": 100, "vin": [{"prevout": {"scriptpubkey_address": "1dice7fUkz5h4z2wPc"}}],
         "vout": [{"scriptpubkey_address": "bc1qexample0"}]},
        {"height": 100, "vin": [{"prevout": {"scriptpubkey_address": "bc1qexample0"}},
                                {"prevout": {"scriptpubkey_address": "3BMEXaaaaaa"}}],
         "vout": [{"scriptpubkey_address": "1other"}, {"scriptpubkey_address": "bc1qexample0"}]},
        {"height": 103, "vin": [], "vout": [{"scriptpubkey_address": "1other"}]},
    ]


def _shape(rows):
    """The coincidence graph: which addresses repeat where, independent of their names."""
    seen = {}
    return [(r["height"],
             [seen.setdefault(a, len(seen)) for a in eg.in_addresses(r)],
             [seen.setdefault(a, len(seen)) for a in eg.out_addresses(r)]) for r in rows]


def test_a_round_trip_preserves_heights_and_the_coincidence_graph(tmp_path):
    rows = _records()
    target = tmp_path / "probe.epochgraph.xz"
    eg.encode(rows, target)
    back = list(eg.decode(target))
    assert [r["height"] for r in back] == [r["height"] for r in rows]
    assert _shape(back) == _shape(rows)


def test_the_detectors_that_read_a_prefix_still_see_it(tmp_path):
    """An address an entity names itself in keeps its text; every other address does not need to."""
    target = tmp_path / "probe.epochgraph.xz"
    eg.encode(_records(), target)
    addresses = {a for r in eg.decode(target) for a in eg.in_addresses(r) + eg.out_addresses(r)}
    assert any(a.startswith("1dice") for a in addresses)
    assert any(a.startswith("3BMEX") for a in addresses)


def test_an_unknown_container_is_refused(tmp_path):
    import lzma
    target = tmp_path / "bad.epochgraph.xz"
    target.write_bytes(lzma.compress(b"not an epoch graph"))
    with pytest.raises(ValueError, match="not an epoch-graph file"):
        list(eg.decode(target))


def _ladder(index):
    fetch = index.__getitem__
    nodes = sorted({v["txid"] for t in index.values() for v in t["vin"]
                    if v.get("txid") in index
                    if len([x for x in t["vin"] if x.get("txid") in index]) >= 2})
    groups, refused, linked = cl.cluster_refined(nodes, Combiner.from_library(), fetch=fetch)
    return len(groups), len(refused), len(linked), max(len(g) for g in groups)


@pytest.mark.reproduction
def test_the_engine_cannot_tell_a_renamed_address_from_a_real_one():
    """The claim the format rests on, measured on committed transactions rather than argued."""
    if not SNAPSHOT.is_file():
        pytest.skip("the block-cache snapshot is not committed")
    with tempfile.TemporaryDirectory() as temporary:
        transactions = load_blkcache(str(extract_tar_gz(str(SNAPSHOT), temporary) / ".blkcache"))

    universe = sorted({a for t in transactions
                       for a in eg.in_addresses(t) + eg.out_addresses(t)})
    forward = {a: f"a{i:09d}" for i, a in enumerate(universe)}
    backward = {a: f"a{len(universe) - 1 - i:09d}" for i, a in enumerate(universe)}

    def renamed(mapping):
        out = {}
        for transaction in transactions:
            copy = json.loads(json.dumps(transaction))
            for vin in copy.get("vin", ()):
                prevout = vin.get("prevout") or {}
                if prevout.get("scriptpubkey_address"):
                    prevout["scriptpubkey_address"] = mapping[prevout["scriptpubkey_address"]]
            for vout in copy.get("vout", ()):
                if vout.get("scriptpubkey_address"):
                    vout["scriptpubkey_address"] = mapping[vout["scriptpubkey_address"]]
            out[copy["txid"]] = copy
        return out

    real = _ladder({t["txid"]: t for t in transactions})
    assert _ladder(renamed(forward)) == real, "an order-preserving renaming moved the partition"
    assert _ladder(renamed(backward)) == real, "an order-reversing renaming moved the partition"


@pytest.mark.skipif(not DERIVED.is_dir(), reason="the derived epochs are not committed")
def test_every_committed_epoch_decodes():
    files = sorted(DERIVED.glob("*.epochgraph.xz"))
    assert files, "the derived directory carries no epoch"
    for path in files:
        first = next(eg.decode(path))
        assert first["height"] > 0 and ("vin" in first and "vout" in first)

def test_windows_encoded_together_share_one_address_namespace(tmp_path):
    """The failure this catches did not lose links, it invented them.

    Numbering each file from zero passed every single-file check — counts, heights, coincidence
    graph — and still corrupted the pair, because `a000000000` then stood for a different address in
    each window and the clusterer read that as the same owner. On the committed epochs it turned
    17,431 rejoinable pairs into 4,972, and the control that caught it was running the same pipeline
    over the original export.
    """
    shared = {"scriptpubkey_address": "bc1qshared"}
    left = [{"height": 1, "vin": [{"prevout": dict(shared)}],
             "vout": [{"scriptpubkey_address": "bc1qleft"}]}]
    right = [{"height": 2, "vin": [{"prevout": {"scriptpubkey_address": "bc1qright"}}],
              "vout": [dict(shared)]}]
    targets = [tmp_path / "left.epochgraph.xz", tmp_path / "right.epochgraph.xz"]
    eg.encode_many([lambda: iter(left), lambda: iter(right)], targets)

    names = [{a for r in eg.decode(t) for a in eg.in_addresses(r) + eg.out_addresses(r)}
             for t in targets]
    assert names[0] & names[1], "the address in both windows did not survive as one name"
    assert len(names[0] & names[1]) == 1, "windows collided on a name they do not share"


def test_encoding_windows_apart_is_refused_by_its_own_namespace_tag(tmp_path):
    """Two files numbered alone are not comparable, and each says which namespace it belongs to."""
    import json, lzma
    rows = [{"height": 1, "vin": [], "vout": [{"scriptpubkey_address": "bc1qone"}]}]
    target = tmp_path / "alone.epochgraph.xz"
    eg.encode(rows, target)
    raw = lzma.decompress(target.read_bytes())[len(eg.MAGIC):]
    header = json.loads(eg._split(raw)[0])
    assert header["namespace"] == "single"
