"""De-mix a real JoinMarket coinjoin (0cb4870c...856bbf, 11 participants). Matches each maker's input
to mix + change - fee and prints the recovered participants and fees. Self-contained (amounts inlined).
Run: python3 examples/coinjoin_demix_demo.py"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster.coinjoin_demix import coinjoin_demix

JM_IN = [2096019783, 771789096, 119639941, 107180297, 97138563, 16543929,
         14482802, 14401514, 9396936, 6378734, 5637331, 807203]
JM_OUT = [6357366] * 11 + [2089662830, 765432353, 113283033, 100823618, 90781833,
                           10187122, 8125627, 8045121, 3044723, 87861]

if __name__ == "__main__":
    assign = coinjoin_demix(JM_IN, JM_OUT)
    mix = Counter(JM_OUT).most_common(1)[0][0]
    print(f"mix denomination: {mix}   inputs: {len(JM_IN)}   participants recovered: {len(assign)}")
    for i in sorted(assign):
        change = assign[i]
        print(f"  input {JM_IN[i]:>12}  = mix + change {change:>12}  - fee {mix + change - JM_IN[i]}")
