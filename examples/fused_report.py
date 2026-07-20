"""End-to-end demo of the fused measurement report on a real mainnet coinjoin.

Build the dss module first (same venv):
    (cd ../dense-subset-sum && maturin develop --release)
Run from the decluster repo root:
    python -m examples.fused_report [txid]

A dense coinjoin exceeds dss's LINK_GUARD, so pairwise_link_prob returns None and the target walk
truncates at the coinjoin itself (target becomes its own absorber, shannon 0, truncated 1) — the
correct refuse behaviour, not a bug. Pass a smaller txid to see a non-trivial provenance walk."""
import sys
from decluster.fetch import fetch_tx
from decluster import report as R

# A real mainnet coinjoin (285 outputs); bounded to one output for a fast, readable demo.
DEFAULT_TXID = "21bebd5b14a1205da9a97071b6bf4970f36e780cf13dd96a19251a9e2980e1d5"


def main(argv):
    try:
        import dss  # noqa: F401
    except ImportError:
        print("dss module not built — run `maturin develop --release` in ../dense-subset-sum "
              "with this venv active, then retry.")
        return 1
    txid = argv[1] if len(argv) > 1 else DEFAULT_TXID
    tx = fetch_tx(txid)
    rep = R.report(tx, targets=[0])     # one output, real dss oracles
    R.print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
