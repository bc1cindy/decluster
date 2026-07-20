import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.subsetsum import amount_refuse_demix, DEMIX_REFUSE_BITS

# a small JoinMarket-shaped coinjoin: 3 single-input makers A,B,C (input = mix 100 + change - 1),
# changes spaced far apart, plus an unmatched input D (the taker).
CJ = {"vin": [{"txid": "A", "prevout": {"value": 100099}},
              {"txid": "B", "prevout": {"value": 50099}},
              {"txid": "C", "prevout": {"value": 10099}},
              {"txid": "D", "prevout": {"value": 5000}}],
      "vout": [{"value": 100}, {"value": 100}, {"value": 100},
               {"value": 100000}, {"value": 50000}, {"value": 10000}]}


def test_different_participants_returns_refuse_bits():
    assert amount_refuse_demix(CJ, "A", "B") == DEMIX_REFUSE_BITS      # matched to different changes


def test_unmatched_input_abstains():
    assert amount_refuse_demix(CJ, "A", "D") == 0.0                  # D (taker) is not matched


def test_batch_payment_abstains():
    tx = {"vin": [{"txid": "A", "prevout": {"value": 2000000}},
                  {"txid": "B", "prevout": {"value": 1090000}}],
          "vout": [{"value": 1000000}, {"value": 1000000}, {"value": 1000000}, {"value": 80000}]}
    assert amount_refuse_demix(tx, "A", "B") == 0.0


def test_pair_not_both_inputs_abstains():
    tx = {"vin": [{"txid": "A", "prevout": {"value": 10}}], "vout": [{"value": 9}]}
    assert amount_refuse_demix(tx, "A", "Z") == 0.0


def test_refuse_bits_is_strong_negative():
    assert DEMIX_REFUSE_BITS == -12.0
