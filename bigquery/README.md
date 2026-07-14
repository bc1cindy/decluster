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

## What scales here vs what doesn't (honest)

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
