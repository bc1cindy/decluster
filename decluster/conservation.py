"""Trace the value of coinjoin outputs by conservation alone.

If a set of equal outputs is worth more than every other participant brought to
the round, the excess had to *come from* the one participant whose input we can
name. No model of the client is involved: not the denomination lattice, not the
decomposer, not fee accounting beyond a conservative floor. Just arithmetic on
what the transaction shows.

What that establishes is provenance of value, and only that. It is not ownership,
and the gap between the two is the whole reason multi-party protocols are built:
under net settlement a participant may both pay and receive inside one round, so
their satoshi legitimately end up in a counterparty's output and the surplus is
forced onto their *input* without any output being theirs. The inference to
ownership needs the extra premise that every participant's sub-transaction is
self-funded -- true of a plain batch, false of anything that settles obligations,
and the adversary cannot assume its absence from a protocol that permits it.

So this is refusal-shaped in the sense PAPER §1 requires: it eliminates the
reading that none of that value came from the named participant. Reporting it as
"these outputs are theirs" overstates it by exactly one assumption.

The bound is deliberately conservative in one direction. Output fees are ignored,
which understates what the other participants must have paid, so the count
returned is a floor. Any real fee makes it larger, never smaller.
"""

def others_input(total_input, known_input):
    """What every participant other than the known one brought to the round."""
    return max(0, total_input - known_input)


def forced_count(total_input, known_input, output_value, output_count):
    """How many outputs of `output_value` the known participant must have funded.

    The others can fund at most `others_input // output_value` of them. Anything
    beyond that has no other source. Returns 0 when the others could have funded
    them all, which is the uninformative case and by far the common one.
    """
    if output_value <= 0 or output_count <= 0:
        return 0
    affordable = others_input(total_input, known_input) // output_value
    return max(0, output_count - affordable)


def forced_in_round(tx, known_input, min_count=1):
    """Every output value in `tx` whose funding conservation traces to the known input.

    Returns `[(value, forced, present)]`, largest first: `forced` of the `present`
    outputs at that value could not have been funded by anyone else. That is a claim
    about where the satoshi came from, not about who holds the outputs -- see the
    module docstring on why net settlement separates the two. `min_count` filters out
    values that force fewer than that many.

    Empty is the expected result. It takes a participant large relative to the
    round for the inequality to bite at all.
    """
    total = sum(v["prevout"]["value"] for v in tx.get("vin", []) if "prevout" in v)
    counts = {}
    for o in tx.get("vout", []):
        counts[o["value"]] = counts.get(o["value"], 0) + 1
    out = []
    for value, present in counts.items():
        forced = forced_count(total, known_input, value, present)
        if forced >= min_count:
            out.append((value, forced, present))
    out.sort(key=lambda r: -r[0])
    return out


def forced_value(tx, known_input, min_count=1):
    """Total satoshi in this round whose funding conservation traces to the known input."""
    return sum(value * forced for value, forced, _ in forced_in_round(tx, known_input, min_count))


def slack_to_force_one_more(total_input, known_input, output_value, output_count):
    """How much more the others would have needed to explain one further output.

    Reads as the margin of the argument: a large number means the conclusion is
    not near a boundary, and rounding or an unmodelled fee cannot overturn it.
    Returns None when nothing is forced.
    """
    forced = forced_count(total_input, known_input, output_value, output_count)
    if forced == 0:
        return None
    affordable = others_input(total_input, known_input) // output_value
    needed_for_one_more = (affordable + 1) * output_value
    return needed_for_one_more - others_input(total_input, known_input)


def forced_satoshi(total_input, known_input, output_values):
    """Satoshi in this set of outputs that cannot have come from anyone else."""
    return max(0, sum(output_values) - others_input(total_input, known_input))


def min_coins_for(satoshi, output_values):
    """Fewest coins from the set that can cover `satoshi`, largest first.

    A floor on how many of these outputs are the known participant's. Taking the
    largest first is what makes it a floor: any other selection needs at least as
    many coins to reach the same sum.
    """
    if satoshi <= 0:
        return 0
    taken = 0
    running = 0
    for value in sorted(output_values, reverse=True):
        if running >= satoshi:
            break
        running += value
        taken += 1
    return taken if running >= satoshi else len(output_values)


def forced_prefixes(tx, known_input):
    """The conservation bound over growing sets of the largest output values.

    `forced_in_round` tests one value at a time, which names *which* outputs are
    forced but forces the least. Pooling the largest values forces more satoshi
    and fewer identifiable coins — the excess could be any coins of the pool. Both
    readings are sound; they answer different questions, so both are reported.

    Returns `[(values, satoshi, coins, pool)]`, one row per prefix of the distinct
    output values taken largest-first: `satoshi` cannot come from anyone else, and
    covering it takes at least `coins` of the `pool` outputs in that prefix.
    """
    total = sum(v["prevout"]["value"] for v in tx.get("vin", []) if "prevout" in v)
    counts = {}
    for o in tx.get("vout", []):
        counts[o["value"]] = counts.get(o["value"], 0) + 1

    rows = []
    chosen = []
    for value in sorted(counts, reverse=True):
        chosen.append(value)
        pooled = [v for value_ in chosen for v in [value_] * counts[value_]]
        satoshi = forced_satoshi(total, known_input, pooled)
        if satoshi <= 0:
            continue
        rows.append((list(chosen), satoshi, min_coins_for(satoshi, pooled), len(pooled)))
    return rows
