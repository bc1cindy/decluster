"""3-axis engine combiner vs. 23-axis LibraryScorer on the merged-transaction anchor `931d6627` (offline;
both txs are cached under .cache/). Scores the same Cake<->sender edge two ways to check whether the
paper's PAPER.md §4 claim (plugging the 23-axis model into the engine resurrects the false merge) is a
real, measured number rather than an invented one.

Reproduce: ./.venv/bin/python examples/three_vs_23_axes.py
Regression-guarded by tests/test_wp4.py (3-axis refusal) and tests/test_fingerprint_validate.py (23-axis
scorer construction); this script is the first place the two are compared head-to-head on this anchor."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster import fetch_tx
from decluster.combiner import Combiner
from decluster.fingerprint_validate import LibraryScorer

CAKE = "0a568e3ae6fa6bf34ce8925266ac2cdb1668c723980398d9c613d67d72b39729"
SENDER = "91106666451dc43a0e3f78b325764251e205b39d7e9498948885678616ba719a"


def main():
    cake, sender = fetch_tx(CAKE), fetch_tx(SENDER)

    engine3 = Combiner.from_library()
    s3 = engine3.score(sender, cake)

    engine23 = LibraryScorer()
    s23, rows = engine23.score(sender, cake, explain=True)

    print(f"3-axis Combiner.from_library() score (sender <-> Cake):  {s3:+.2f} bits")
    print(f"23-axis LibraryScorer score        (sender <-> Cake):  {s23:+.2f} bits")
    print()
    print("23-axis per-axis breakdown:")
    for name, va, vb, w in rows:
        print(f"  {name:24} {va!s:22} {vb!s:22} {'abstain' if w is None else f'{w:+.2f}'}")

    print()
    verdict3 = "REFUSE" if s3 < 0 else "LINK"
    verdict23 = "REFUSE" if s23 < 0 else "LINK"
    print(f"3-axis verdict:  {verdict3} ({s3:+.2f} bits) -> matches the correct partition (§6)")
    print(f"23-axis verdict: {verdict23} ({s23:+.2f} bits) -> "
          f"{'re-merges the false Cake<->sender link' if s23 > 0 else 'agrees with the 3-axis refusal'}")


if __name__ == "__main__":
    main()
