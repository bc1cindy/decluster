import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.coinjoin_demix import coinjoin_demix

# Real JoinMarket coinjoin 0cb4870c...856bbf: 11 mix outputs of 6357366 + 10 changes, 12 inputs.
JM_IN = [2096019783, 771789096, 119639941, 107180297, 97138563, 16543929,
         14482802, 14401514, 9396936, 6378734, 5637331, 807203]
JM_OUT = [6357366] * 11 + [2089662830, 765432353, 113283033, 100823618, 90781833,
                           10187122, 8125627, 8045121, 3044723, 87861]


def test_demix_real_joinmarket_recovers_eight_makers():
    assign = coinjoin_demix(JM_IN, JM_OUT)
    assert len(assign) == 8                       # 8 single-input makers matched uniquely
    assert set(assign) == {0, 1, 2, 3, 4, 5, 6, 7}
    assert assign[0] == 2089662830                # largest input <-> largest change


def test_demix_three_maker_synthetic():
    # changes spaced far apart (> fee_cap) so each input matches one change; input = mix + change - 1.
    assign = coinjoin_demix([100099, 50099, 10099], [100, 100, 100, 100000, 50000, 10000])
    assert assign == {0: 100000, 1: 50000, 2: 10000}


def test_demix_batch_payment_abstains():
    # 3 equal payments + change, single owner: inputs exceed mix+change, no valid maker fee.
    assert coinjoin_demix([2000000, 1090000], [1000000, 1000000, 1000000, 80000]) == {}


def test_demix_no_mix_denomination_abstains():
    assert coinjoin_demix([10, 20], [8, 18]) == {}
