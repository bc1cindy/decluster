"""Memory-scalable global CIOH clustering for multi-epoch slices too large to hold in RAM.

`views.cluster_addresses` materialises the whole sample and a string-keyed union-find, which is fine
for ~1M transactions but not for a multi-month, tens-of-millions-of-address slice on a small machine.
This streams the transactions from disk and runs union-find over 64-bit address hashes, so memory
scales with the union-participating address set rather than with the transaction count.

It reproduces the refuse-guarded clustering exactly on the address-only slices this project collects
(no input/output values, so the de-mix refinement is inert and refusal reduces to skipping the
coinjoin shape): skip a transaction whose shape is many-in-many-out, otherwise union all of its input
addresses. `test`-validated to produce the identical partition to `views.cluster_addresses` on a real
slice.
"""
import hashlib
import json
import gzip
from array import array

from .monitor import COINJOIN_MIN_PARTICIPANTS, is_coinjoin


def ahash(a):
    """Address to 64-bit id. Collision probability is negligible at the address counts here."""
    return int.from_bytes(hashlib.blake2b(a.encode(), digest_size=8).digest(), "big")


def stream_txs(paths):
    for p in paths:
        opener = gzip.open if str(p).endswith(".gz") else open
        with opener(p, "rt") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def _in_addr_hashes(tx):
    hs = []
    for v in tx.get("vin", []):
        a = (v.get("prevout") or {}).get("scriptpubkey_address")
        if a:
            hs.append(ahash(a))
    return hs


class ScaleClustering:
    """Union-find over address hashes. `cid(address)` returns the cluster root (an int) for a
    union-participating address, or the address itself for a singleton, matching the semantics
    `contraction.contract` expects from a partial `lookup` (`lookup.get(a, a)`)."""

    def __init__(self, parent):
        self._parent = parent

    def _find(self, x):
        p = self._parent
        r = x
        while p[r] != r:
            r = p[r]
        while p[x] != r:
            p[x], x = r, p[x]
        return r

    def get(self, addr, default=None):
        h = ahash(addr)
        if h in self._parent:
            return self._find(h)
        return default

    def n_clusters(self):
        return len({self._find(x) for x in self._parent})

    def map_many(self, addresses):
        """Return address -> cluster id, preserving addresses outside the union-find as singletons."""
        return {address: self.get(address, address) for address in addresses}


def cluster_scale(paths, refuse=True, coinjoin_min=COINJOIN_MIN_PARTICIPANTS):
    return cluster_scale_stream(stream_txs(paths), refuse=refuse, coinjoin_min=coinjoin_min)


def cluster_scale_stream(txs, refuse=True, coinjoin_min=COINJOIN_MIN_PARTICIPANTS):
    """Dictionary-backed reference implementation over a transaction iterator."""
    parent = {}

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    for tx in txs:
        if refuse and is_coinjoin(tx, coinjoin_min):
            continue
        hs = _in_addr_hashes(tx)
        if len(hs) < 2:
            continue
        for h in hs:
            if h not in parent:
                parent[h] = h
        r0 = find(hs[0])
        for h in hs[1:]:
            r = find(h)
            if r != r0:
                parent[r] = r0
    return ScaleClustering(parent)


def cluster_scale_np(paths, refuse=True, coinjoin_min=COINJOIN_MIN_PARTICIPANTS):
    """Dense-integer union-find over 64-bit address hashes, the BlockSci-style compact
    representation: instead of a Python dict {hash: hash}, map the
    union-participating hashes to dense indices via a sorted int64 array + searchsorted, and
    run union-find on an int32 parent array. The final partition is compact, but building the
    global unique-address table requires retaining an edge buffer; measured end-to-end memory
    is therefore workload-dependent (about 20% lower at 3M transactions, and slightly higher at
    1M). Produces the identical partition (validated in tests)."""
    return cluster_scale_np_stream(stream_txs(paths), refuse=refuse, coinjoin_min=coinjoin_min)


def cluster_scale_np_stream(txs, refuse=True, coinjoin_min=COINJOIN_MIN_PARTICIPANTS,
                            edge_chunk=1_000_000):
    """Compact clustering over an arbitrary transaction iterator.

    Edges are stored in an interleaved native uint64 buffer rather than Python integer lists.
    Dense-index lookup is performed a chunk at a time, so the two full-size `searchsorted` index
    arrays and their accidental `.tolist()` copies never coexist in memory.
    """
    import numpy as np
    edges = array("Q")
    for tx in txs:
        if refuse and is_coinjoin(tx, coinjoin_min):
            continue
        hs = _in_addr_hashes(tx)
        if len(hs) < 2:
            continue
        h0 = hs[0]
        for h in hs[1:]:
            edges.extend((h0, h))
    if not edges:
        return NpClustering(np.empty(0, np.uint64), np.empty(0, np.int32))
    edge_view = np.frombuffer(edges, dtype=np.uint64).reshape(-1, 2)
    uniq = np.unique(edge_view)
    parent = np.arange(len(uniq), dtype=np.int32)

    def find(x):
        r = x
        while parent[r] != r:
            r = parent[r]
        while parent[x] != r:
            parent[x], x = r, parent[x]
        return r

    for lo in range(0, len(edge_view), edge_chunk):
        block = edge_view[lo:lo + edge_chunk]
        src_idx = np.searchsorted(uniq, block[:, 0])
        dst_idx = np.searchsorted(uniq, block[:, 1])
        for a, b in zip(src_idx, dst_idx):
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[ra] = rb
        del src_idx, dst_idx
    del edge_view, edges
    root = np.fromiter((find(i) for i in range(len(uniq))), np.int32, len(uniq))
    return NpClustering(uniq, root)


class NpClustering:
    """`get(address)` -> a stable cluster id (the root's dense index) for a union-participating
    address, else `default`. Same `contraction.contract` semantics as `ScaleClustering`, backed by a
    sorted-hash array instead of a dict."""

    def __init__(self, uniq, root):
        self._u = uniq
        self._r = root

    def get(self, addr, default=None):
        import numpy as np
        if not len(self._u):
            return default
        h = ahash(addr)
        pos = int(np.searchsorted(self._u, h))
        if pos < len(self._u) and int(self._u[pos]) == h:
            return int(self._r[pos])
        return default

    def n_clusters(self):
        import numpy as np
        return int(len(np.unique(self._r)))

    def map_many(self, addresses):
        """Vectorized dense lookup; hashing remains streaming but searchsorted crosses Python once."""
        import numpy as np
        addresses = list(addresses)
        if not addresses or not len(self._u):
            return {address: address for address in addresses}
        hashes = np.frombuffer(array("Q", (ahash(address) for address in addresses)),
                               dtype=np.uint64)
        positions = np.searchsorted(self._u, hashes)
        out = {}
        for address, hashed, pos in zip(addresses, hashes, positions):
            index = int(pos)
            out[address] = (int(self._r[index])
                            if index < len(self._u) and self._u[index] == hashed else address)
        return out
