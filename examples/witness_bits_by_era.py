"""Re-measure the witness-axis bits per era on the multi-era .blkcache, vs the library's
current single-snapshot bits. Read-only: reports a table, never mutates library.py (adopting
new bits would shift the locked validation headline — that's a separate decision).

Bits = -log2(share) within an era's tx population, matching the library's provenance method.
Witness exists only post-SegWit, so pre-segwit rows are degenerate (~all `na`) by protocol.

usage: python3 -m examples.witness_bits_by_era
"""
import math
from collections import Counter
from decluster import extractors, library
from decluster.fingerprint_validate import load_blkcache
from examples.era_crawler import era, ERAS

WITNESS_AXES = ["low_r", "sighash", "pubkey_compression", "nested_segwit", "multisig"]
ERA_NAMES = [name for name, _, _ in ERAS]


def _height(tx):
    return int((tx.get("status") or {}).get("block_height") or tx.get("height") or 0)


def measure(txs):
    """axis -> era -> {value: (count, bits)} over that era's full tx population."""
    by_era = {name: [] for name in ERA_NAMES}
    for tx in txs:
        h = _height(tx)
        if h:
            by_era.setdefault(era(h), []).append(tx)
    out = {}
    for axis in WITNESS_AXES:
        fn = getattr(extractors, "x_" + axis)
        out[axis] = {}
        for name in ERA_NAMES:
            pop = by_era.get(name, [])
            if not pop:
                continue
            c = Counter(fn(tx) for tx in pop)
            out[axis][name] = {v: (n, -math.log2(n / len(pop))) for v, n in c.items()}
    return out, {name: len(by_era.get(name, [])) for name in ERA_NAMES}


def report(txs):
    out, sizes = measure(txs)
    print("era sizes:", "  ".join(f"{name}={sizes[name]}" for name in ERA_NAMES), "\n")
    for axis in WITNESS_AXES:
        libbits = (library._BY.get(axis) or {}).get("bits") or {}
        print(f"== {axis} ==  (library snapshot: "
              + ", ".join(f"{v}={b}" for v, b in libbits.items()) + ")")
        values = sorted({v for era_d in out[axis].values() for v in era_d})
        header = "  ".join(f"{name}(bits)" for name in ERA_NAMES if name != "pre-segwit")
        print(f"  {'value':22} {header}   library")
        for v in values:
            cells = []
            for name in ERA_NAMES:
                if name == "pre-segwit":
                    continue
                cell = out[axis].get(name, {}).get(v)
                cells.append(f"{cell[1]:5.2f}" if cell else "   — ")
            lib = f"{libbits[v]:.2f}" if v in libbits else "—"
            print(f"  {v:22} {'   '.join(cells)}      {lib}")
        print()


if __name__ == "__main__":
    txs = load_blkcache()
    print(f"# {len(txs)} txs in .blkcache\n")
    report(txs)
