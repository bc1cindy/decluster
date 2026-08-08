-- Ancestry slice for §04 provenance-walk validation at scale.
--
-- Unlike slice.sql / slice_values.sql (a 1-day window, tuned for change labels), this exports a
-- WIDER contiguous window so that a target coin's ANCESTORS are in-sample to depth >= 4 — the
-- backward provenance walk (decluster.ancestry.build_extended_graph) needs each ancestor tx present,
-- and a 1-day window's parents mostly live BEFORE the window (poor backward connectivity, as measured
-- on sample.ndjson: only ~1% of vin-parents were in-file).
--
-- Strategy: pick seed targets in the LAST day of the window; the window extends BACKWARD from them,
-- so an end-of-window tx's depth-4..5 ancestry lands inside the window. Widen the window -> deeper
-- in-sample ancestry (and more bytes). The harness reports the ACTUAL connectivity/coverage after
-- export, so tune from that.
--
-- Carries input+output VALUES (the dss link oracle needs them), addresses (co-spend / change /
-- same-owner labels), sequence/version/locktime, and forward-spend refs (Möser-Narayanan change
-- labels: change = the output that co-spends with the inputs inside the window). Same JSON schema the
-- Python pipeline already consumes.
--
-- COST / FREE-TIER: block_timestamp_month is the partition column. Filtering it with LITERAL dates
-- (a BETWEEN range) prunes partitions at plan time — do NOT use DECLARE variables (a runtime variable
-- defeats pruning and scans ~780 GB). The BETWEEN below covers the 7-day window robustly whether the
-- table is month- or day-partitioned. Byte cost: if month-partitioned, a 7-day window within one month
-- scans ~the same as 1 day (same partition); if day-partitioned, ~7x. Either way, CHECK the
-- "bytes processed" estimate in the console BEFORE running; narrow the window (edit the two
-- block_timestamp literals AND the block_timestamp_month BETWEEN bounds together) if it is too large.
--
-- Export as NEWLINE-DELIMITED JSON to ancestry_slice.ndjson, then hand the path to the harness:
--   .venv/bin/python -m examples.anonymity_set_scale ancestry_slice.ndjson
--
-- Honest bias (same as slice.sql): only change spent WITHIN the window is revealed, so same-owner
-- labels skew to fast-spending wallets (services, peel chains). Widening the window reduces it.

SELECT TO_JSON_STRING(STRUCT(
  t.hash AS txid,
  t.block_number AS height,
  t.block_timestamp AS block_time,
  t.version AS version,
  t.lock_time AS locktime,
  t.is_coinbase AS is_coinbase,
  ARRAY(
    SELECT AS STRUCT
      i.spent_transaction_hash AS txid,
      i.spent_output_index      AS vout,
      i.sequence                AS sequence,
      STRUCT(
        i.value AS value,
        (SELECT a FROM UNNEST(i.addresses) a LIMIT 1) AS scriptpubkey_address
      ) AS prevout
    FROM UNNEST(t.inputs) i
  ) AS vin,
  ARRAY(
    SELECT AS STRUCT
      o.value AS value,
      o.index AS n,
      (SELECT a FROM UNNEST(o.addresses) a LIMIT 1) AS scriptpubkey_address
    FROM UNNEST(t.outputs) o
  ) AS vout
)) AS row
FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
-- 7-day window [2024-06-01, 2024-06-08). The BETWEEN on the partition column prunes to the covered
-- partitions (robust to month- or day-partitioning); the block_timestamp range narrows to the exact
-- 7 days. Move/resize the window by editing BOTH pairs of literals together. Narrow if bytes too high.
WHERE t.block_timestamp_month BETWEEN DATE('2024-06-01') AND DATE('2024-06-08')
  AND t.block_timestamp >= TIMESTAMP('2024-06-01') AND t.block_timestamp < TIMESTAMP('2024-06-08')
-- coinbase txs are kept: they are the walk's absorbing origins (a real boundary, not a truncation).
