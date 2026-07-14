"""test fee-rate and input-script-type extractors"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_x_fee_rate():
    from decluster.extractors import x_fee_rate
    assert x_fee_rate({"fee": 200, "weight": 400}) == "round"      # 200/(400/4)=2.0 sat/vB
    assert x_fee_rate({"fee": 220, "weight": 437}) == "precise"    # 2.01 sat/vB (estimator)
    assert x_fee_rate({"fee": None, "weight": 400}) == "na"

def test_x_input_script_type():
    from decluster.extractors import x_input_script_type
    tx = {"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}},
                  {"prevout": {"scriptpubkey_type": "v0_p2wpkh"}}]}
    assert x_input_script_type(tx) == "uniform_v0_p2wpkh"
    tx2 = {"vin": [{"prevout": {"scriptpubkey_type": "v0_p2wpkh"}},
                   {"prevout": {"scriptpubkey_type": "v1_p2tr"}}]}
    assert x_input_script_type(tx2) == "mixed"
    assert x_input_script_type({"vin": [{}]}) == "na"

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print(f"  ok  {name}")
    print("2 passed")
