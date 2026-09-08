"""The address graph of a block window, in a form small enough to commit.

The weekly 2016 export ships 977 MB of NDJSON that this repository cannot carry: every file is
larger than the 100 MB a git host accepts, and one of them is twice that. What the pipeline reads
from it is narrower than what it stores — `height`, the input addresses and the output addresses.
The transaction id is never read: contraction spans heights and the address helpers take addresses,
so 64 hex characters per record travel for nothing.

Addresses are the remaining bulk, and they do not need to be themselves. Clustering asks which
addresses coincide, not what they are called, and the pipeline's output is invariant under any
bijective renaming — verified against the committed block cache under both an order-preserving and
an order-reversing map. So an address becomes an integer, and only the ones a name-emitting detector
can recognise by prefix keep their text: on the first epoch that is 94 of 1,788,311.

What this costs is honesty about what the file now is. It is a derived dataset, not a chain export:
a reader cannot recover the addresses from it, and verifies it by running the query and the
transform rather than by inspecting the bytes.
"""

from __future__ import annotations

import json
import lzma

MAGIC = b"decluster/epoch-graph/1\n"
# The prefixes `entities` matches on. A detector that reads values or scripts cannot fire on this
# export at all, so keeping the prefix is enough to keep every detector it can carry.
NAMED_PREFIXES = ("3BMEX", "bc1qmex", "1dice")


def _varint(values):
    out = bytearray()
    for value in values:
        value = (value << 1) ^ (value >> 63) if value < 0 else value << 1
        while value >= 0x80:
            out.append((value & 0x7F) | 0x80)
            value >>= 7
        out.append(value)
    return bytes(out)


def _read_varints(data, count):
    values, shift, current, index = [], 0, 0, 0
    for byte in data:
        current |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
            continue
        values.append(-(current + 1) // 2 if current & 1 else current >> 1)
        shift = current = 0
        index += 1
        if index == count:
            break
    return values


def _sections(blobs):
    out = bytearray()
    for blob in blobs:
        out += len(blob).to_bytes(8, "little") + blob
    return bytes(out)


def _split(data):
    blobs, offset = [], 0
    while offset < len(data):
        size = int.from_bytes(data[offset:offset + 8], "little")
        offset += 8
        blobs.append(data[offset:offset + size])
        offset += size
    return blobs


def in_addresses(transaction):
    return [address for vin in transaction.get("vin", ())
            if (address := (vin.get("prevout") or {}).get("scriptpubkey_address"))]


def out_addresses(transaction):
    return [address for vout in transaction.get("vout", ())
            if (address := vout.get("scriptpubkey_address"))]


def encode(transactions, path, *, preset=6):
    """Write the address graph of `transactions` to `path`. Returns what it recorded."""
    identifiers, named = {}, {}
    heights, ins, outs, stream = [], [], [], []
    for transaction in transactions:
        inputs, outputs = in_addresses(transaction), out_addresses(transaction)
        heights.append(transaction.get("height", 0))
        ins.append(len(inputs))
        outs.append(len(outputs))
        for address in inputs + outputs:
            identifier = identifiers.get(address)
            if identifier is None:
                identifier = identifiers[address] = len(identifiers)
                if address.startswith(NAMED_PREFIXES):
                    named[identifier] = address
            stream.append(identifier)

    previous = heights[0] if heights else 0
    deltas = []
    for height in heights:
        deltas.append(height - previous)
        previous = height
    payload = _sections([
        json.dumps({"transactions": len(heights), "addresses": len(identifiers),
                    "first_height": heights[0] if heights else 0}, sort_keys=True).encode(),
        _varint(deltas), _varint(ins), _varint(outs), _varint(stream),
        json.dumps(named, sort_keys=True).encode(),
    ])
    with open(path, "wb") as sink:
        sink.write(lzma.compress(MAGIC + payload, preset=preset))
    return {"transactions": len(heights), "addresses": len(identifiers), "named": len(named)}


def decode(path):
    """Yield one transaction dict per record, in the order `encode` received them."""
    with open(path, "rb") as source:
        raw = lzma.decompress(source.read())
    if not raw.startswith(MAGIC):
        raise ValueError(f"{path}: not an epoch-graph file")
    header, deltas, ins, outs, stream, named = _split(raw[len(MAGIC):])
    meta = json.loads(header)
    count = meta["transactions"]
    heights, height = [], meta["first_height"]
    for delta in _read_varints(deltas, count):
        height += delta
        heights.append(height)
    n_in = _read_varints(ins, count)
    n_out = _read_varints(outs, count)
    identifiers = _read_varints(stream, sum(n_in) + sum(n_out))
    labels = {int(k): v for k, v in json.loads(named).items()}
    name = lambda identifier: labels.get(identifier) or f"a{identifier:09d}"

    cursor = 0
    for index in range(count):
        inputs = identifiers[cursor:cursor + n_in[index]]
        cursor += n_in[index]
        outputs = identifiers[cursor:cursor + n_out[index]]
        cursor += n_out[index]
        yield {
            "height": heights[index],
            "vin": [{"prevout": {"scriptpubkey_address": name(i)}} for i in inputs],
            "vout": [{"scriptpubkey_address": name(o)} for o in outputs],
        }
