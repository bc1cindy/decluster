"""rust_schema encoding tests (offline, hand-crafted txs matching the Rust semantics)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.rust_bridge import vector, _bitset, _otype


def _tx(vin, vout, locktime=0):
    return {"vin": vin, "vout": vout, "locktime": locktime}


def _in(seq=0xFFFFFFFF, ptype="v0_p2wpkh", value=1000, txid="aa" * 32, vout=0, addr="A", witness=None):
    d = {"sequence": seq, "vout": vout, "txid": txid,
         "prevout": {"scriptpubkey_type": ptype, "value": value, "scriptpubkey_address": addr}}
    if witness is not None:
        d["witness"] = witness
    return d


def _out(ptype="v0_p2wpkh", value=900, addr="B"):
    return {"scriptpubkey_type": ptype, "value": value, "scriptpubkey_address": addr}


def test_single_input_single_output():
    v = vector(_tx([_in()], [_out()]))
    assert v[0] == 0            # no RBF (seq max)
    assert v[2] == 0            # locktime zero
    assert v[6] == 0            # single output
    assert v[11] == _bitset([0])  # input_order Single
    assert v[8] == _bitset([_otype("v0_p2wpkh")])  # input_types = {P2wpkh}


def test_rbf_and_locktime_axes():
    v = vector(_tx([_in(seq=0xFFFFFFFD)], [_out()], locktime=800000))
    assert v[0] == 1            # signals_rbf (seq < fffffffe)
    assert v[2] == 1            # anti_fee_snipe (locktime != 0)
    assert v[3] == 0            # not optin-without-use (locktime is set)
    assert v[4] == 0            # 0xfffffffd is NOT < 0x80000000 -> no bip68


def test_bip68_with_absolute_locktime():
    v = vector(_tx([_in(seq=0x10)], [_out()], locktime=800000))
    assert v[4] == 1            # relative timelock (seq < 0x80000000) + absolute locktime


def test_optin_without_use():
    v = vector(_tx([_in(seq=0xFFFFFFFD)], [_out()], locktime=0))
    assert v[3] == 1            # RBF signaled but locktime zero


def test_output_structure_and_bitset():
    v = vector(_tx([_in()], [_out("p2pkh"), _out("v1_p2tr"), _out("p2sh")]))
    assert v[6] == 2            # multi (>2 outputs)
    assert v[5] == _bitset([0, 4, 1])  # P2pkh|P2tr|P2sh


def test_mixed_inputs_and_address_reuse():
    tx = _tx([_in(ptype="p2pkh", addr="X", txid="11" * 32),
              _in(ptype="v0_p2wpkh", addr="Y", txid="22" * 32, value=2000)],
             [_out(addr="X")])          # output reuses input address X
    v = vector(tx)
    assert v[9] == 1            # mixed_input_types (p2pkh + p2wpkh)
    assert v[10] == 1           # address_reuse (X in both)


def test_nsequence_class_recovers_cake():
    cake = _tx([_in(seq=0x01, txid="11" * 32), _in(seq=0xFFFFFFFF, txid="22" * 32)], [_out()])
    assert vector(cake)[14] == 0            # cake_group_c
    assert vector(_tx([_in(seq=0xFFFFFFFD)], [_out()]))[14] == 2   # rbf


def test_witness_axes_none_without_witness():
    v = vector(_tx([_in()], [_out()]))   # no witness key
    assert v[1] is None and v[12] is None and v[13] is None


def test_low_r_from_witness():
    # DER sig with r high byte < 0x80 -> low-R. 30 44 02 20 <r 32 bytes, first 7f> ...
    der = "3044" + "0220" + "7f" + "00" * 31 + "0220" + "01" * 32 + "01"
    v = vector(_tx([_in(witness=[der, "02" + "ab" * 32])], [_out()]))
    assert v[1] == 1


def test_score_matches_fellegi_sunter():
    # match on a rare value scores positive; mismatch scores negative
    from decluster.rust_bridge import score
    model = ([{0: 0.9, 1: 0.1}], [0.82], [10.0], 0.95)
    assert score([1], [1], model) > 0          # match on rare (0.1) -> +bits
    assert score([0], [1], model) < 0          # mismatch -> -bits


if __name__ == "__main__":
    fns = [f for k, f in sorted(globals().items()) if k.startswith("test_") and callable(f)]
    for f in fns: f(); print(f"ok  {f.__name__}")
    print(f"\n{len(fns)} passed")
