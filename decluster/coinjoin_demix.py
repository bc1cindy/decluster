"""Coinjoin de-mix: assign inputs to participants by the fixed-denomination identity
`input = mix + change - fee`. Recovers single-input makers of a JoinMarket/Wasabi coinjoin; abstains
on ordinary and batch payments (no mix denomination, or no unique match). Refuse-only signal for the
clusterer via `subsetsum.amount_refuse_demix`."""
from collections import Counter
from functools import lru_cache

DEFAULT_FEE_CAP = 2000           # max maker fee (sats); the uniqueness test is the main guard


def coinjoin_demix(inputs, outputs, fee_cap=DEFAULT_FEE_CAP):
    """{input_index -> participant_id} for inputs matched uniquely (one input <-> one change) under
    `0 < (mix + change) - input <= fee_cap`, where mix is the most common output value (count >= 3).
    participant_id is the change value. Empty when there is no mix denomination or no unique match."""
    return dict(_demix_cached(tuple(inputs), tuple(outputs), fee_cap))   # copy: never expose the cached dict


@lru_cache(maxsize=2048)
def _demix_cached(inputs, outputs, fee_cap):
    if not outputs:
        return {}
    mix, mix_count = Counter(outputs).most_common(1)[0]
    if mix_count < 3:
        return {}
    changes = [c for c in outputs if c != mix]
    valid = {i: [c for c in changes if 0 < (mix + c) - v <= fee_cap]
             for i, v in enumerate(inputs)}
    change_uses = Counter(c for cs in valid.values() for c in cs)
    return {i: cs[0] for i, cs in valid.items()
            if len(cs) == 1 and change_uses[cs[0]] == 1}
