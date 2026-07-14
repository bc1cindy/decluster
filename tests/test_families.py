"""test family fingerprint extractors"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_x_op_return():
    from decluster.extractors import x_op_return
    assert x_op_return({"vout": [{"scriptpubkey_type": "op_return"}, {"scriptpubkey_type": "v0_p2wpkh"}]}) == "has_op_return"
    assert x_op_return({"vout": [{"scriptpubkey_type": "v0_p2wpkh"}]}) == "none"

def test_x_output_encoding():
    from decluster.extractors import x_output_encoding
    assert x_output_encoding({"vout": [{"scriptpubkey_type": "p2pkh"}]}) == "base58"
    assert x_output_encoding({"vout": [{"scriptpubkey_type": "v0_p2wpkh"}]}) == "bech32"
    assert x_output_encoding({"vout": [{"scriptpubkey_type": "v1_p2tr"}]}) == "bech32m"
    assert x_output_encoding({"vout": [{"scriptpubkey_type": "p2pkh"}, {"scriptpubkey_type": "v1_p2tr"}]}) == "mixed"

def test_x_input_types_present():
    from decluster.extractors import x_input_types_present
    assert x_input_types_present({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}}]}) == "v0_p2wpkh"
    assert x_input_types_present({"vin": [{"prevout": {"scriptpubkey_type": "p2sh"}},
                                          {"prevout": {"scriptpubkey_type": "p2pkh"}}]}) == "p2pkh+p2sh"

def test_x_nested_segwit():
    from decluster.extractors import x_nested_segwit
    assert x_nested_segwit({"vin": [{"prevout": {"scriptpubkey_type": "p2sh"}, "witness": ["aa", "bb"]}]}) == "nested_segwit"
    assert x_nested_segwit({"vin": [{"prevout": {"scriptpubkey_type": "p2sh"}, "witness": []}]}) == "none"

def test_x_pubkey_compression():
    from decluster.extractors import x_pubkey_compression
    comp = "02" + "aa"*32   # 33 bytes, 0x02 prefix
    unco = "04" + "bb"*64   # 65 bytes, 0x04 prefix
    assert x_pubkey_compression({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}, "witness": ["30sig", comp]}]}) == "compressed"
    assert x_pubkey_compression({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}, "witness": ["30sig", unco]}]}) == "uncompressed"
    assert x_pubkey_compression({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wsh"}, "witness": ["x"]}]}) == "na"

def test_x_multisig():
    from decluster.extractors import x_multisig
    assert x_multisig({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wsh"}, "witness": ["", "sig", "5221aabbae"]}]}) == "multisig"
    assert x_multisig({"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}, "witness": ["sig", "pk"]}]}) == "none"
    # P2SH legacy multisig: scriptSig ends in the redeemScript's OP_CHECKMULTISIG (ae)
    assert x_multisig({"vin": [{"prevout": {"scriptpubkey_type": "p2sh"}, "scriptsig": "0047522102aabbae"}]}) == "multisig"
    assert x_multisig({"vin": [{"prevout": {"scriptpubkey_type": "p2sh"}, "scriptsig": "160014abcd"}]}) == "none"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("6 passed")
