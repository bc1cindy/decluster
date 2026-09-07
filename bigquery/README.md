# Large-scale fingerprint bits via BigQuery (no archival node)

Compute the per-axis fingerprint bits over a **large uniform mainnet sample (~500k txs)**
using Google's public Bitcoin dataset — no local node, no 600 GB, free tier.

The trick: `sample.sql` exports transactions in the **same JSON schema the Python
extractors already consume**, so we reuse the existing pipeline at scale instead of
re-implementing the fingerprint logic in SQL.

## Steps

1. **Google Cloud account** (free tier) → open the [BigQuery console](https://console.cloud.google.com/bigquery).
2. Paste `bigquery/sample.sql` and **Run**.
   - `TABLESAMPLE SYSTEM (0.05 PERCENT)` reads only ~0.05% of the table's blocks — a
     uniform random sample of ~500k txs, and cheap (well under the 1 TB/month free tier).
   - Bigger/smaller sample: change the percent (0.1 ≈ 1M txs, 0.02 ≈ 200k).
3. **Save results → JSONL** (newline-delimited JSON). Each row is the `row` column (a
   JSON string). Download it as e.g. `sample.ndjson`.
   - Big results: *Save results → BigQuery table*, then *Export → GCS* as JSON, then
     download from the bucket.
4. Run the existing pipeline on it:
   ```bash
   python3 decluster/measure.py sample.ndjson
   ```
   This prints the per-axis bit tables over the whole sample.
5. Send the output back — the `library.py` bits, `RESULTS-wp1a.md`, and `PAPER.md` §5 get
   updated to the large-scale numbers.

## What scales here vs what doesn't

- **Scales (BigQuery, ~500k+):** nSequence, nLockTime, version, fee-rate, input/output
  order, change script type, input script type + presence, output encoding, OP_RETURN,
  io-shape, UIH (real input values), change relations, address reuse — the structural /
  amount / type axes.
- **Does NOT scale here:** low-R, SIGHASH, pubkey compression, multisig — these need
  **witness data**, which the `crypto_bitcoin` schema does not carry, so they read `na`
  from the BigQuery export. They stay measured on the mempool.space sample (thousands),
  documented in the paper.

## Cost / honesty
- `TABLESAMPLE` keeps bytes scanned small (free tier). Confirm the "bytes processed"
  estimate in the console before running.
- ~500k txs is a **large representative sample**, not literally every tx — but for
  calibrating fingerprint frequencies it is publication-solid (rare values become
  estimable). Every-tx exactness would still want an archival node.

## Graph slices vs frequency samples

`sample.sql` is a uniform `TABLESAMPLE`, which is right for calibrating fingerprint
frequencies and **useless for anything about the graph**: a random sample of transactions
is disconnected. Graph work needs a contiguous block range.

| file | what it exports | for |
|---|---|---|
| `sample.sql` | uniform ~0.05 % sample | per-axis fingerprint frequencies |
| `graph.sql` | contiguous range, addresses only, no coinbase | the community-structure probe |
| `slice.sql` | contiguous range, lean, forward-spend links | change-label validation |
| `slice_gate.sql` | aggregates only, no export | go/no-go before paying for a slice |
| `pseudonym_slice.sql` | contiguous range, full schema incl. coinbase | cross-view pseudonym matching |

### Traps this dataset sets, all of them silent

Each of these was hit while building `pseudonym_slice.sql`. None raises an error; each
just produces wrong numbers.

- **Coinbase transactions carry no inputs** (`input_count = 0`), so `UNNEST(inputs)` drops
  them entirely via the implicit cross join, and the coinbase scriptSig is simply not in
  `transactions`. It is in `blocks.coinbase_param`. Without that join, pool detection has
  nothing to fire on.
- **`UNNEST` does not preserve array order.** The input-order and output-order axes and
  BIP-69 all depend on it. `ORDER BY index` is mandatory, not tidiness.
- **Script types use a different vocabulary** (`witness_v0_keyhash`, not `v0_p2wpkh`), and
  **there is no OP_RETURN type at all**: OP_RETURN outputs are reported as `nonstandard`
  (15 916 of 16 024 in a 10-block probe; the other 108 are bare multisig). Untranslated,
  every type and encoding axis reads unknown and the OP_RETURN axis never fires.
- **Filtering on `block_number` alone does not prune partitions.** The filter must be on
  `block_timestamp_month` (`transactions`) or `timestamp_month` (`blocks`).
- **835 blocks are missing above height 959 194** (largest gap 962 010–962 489). A slice
  spanning that range has holes in its graph.

Verified while building it: values are satoshis; 17 of 22 axes fire correctly on the
export. Of the five that do not, `low_r`, `sighash` and `pubkey_compression` abstain
as `na`, but **`multisig` and `nested_segwit` report `none`**, a false negative
rather than a missing value. Exclude those two rather than trusting them.

### Scale of the result

A 10-block probe is 29 213 transactions and 39 MB of JSON, giving 49 109 addresses and
1 727 entities of two or more addresses.

`graph_deanon.build` originally took 2.8 s and 823 MB of RSS on it, because the co-spend
pair set is quadratic in a transaction's input count: one consolidation of 1 059 addresses
contributes ~560 000 pairs on its own. Extrapolated to a 144-block epoch that was ~39 s and
~11.6 GB, which does not fit. `CoSpent` replaces the pair set with address → funded
transactions, answering the same membership query by intersection in linear space, and the
build drops to 0.25 s.

What remains is linear and splits as follows, per 144-block epoch:

| | probe (29 213 txs) | extrapolated to one epoch |
|---|---:|---:|
| parsing the transactions | 190 MB | ~2.7 GB |
| graph structures | 306 MB | ~4.3 GB |
| `build` | 0.25 s | ~4 s |

Time is no longer a concern. Memory is, and it is now the ordinary linear cost of holding
a parsed epoch rather than a quadratic blow-up, so the fix if it binds is a streaming
loader, not a different data structure.

Those figures are for `graph_deanon.build`, the address-level probe. The contraction the
cross-view pipeline actually runs, `views.contract`, is lighter: **800 MB** for a 144-block
view, 653 MB with attributes off, and 624 MB for *both* views once vertices below transfer
count two are dropped.
