-- Go/no-go gate for a 2026 cross-view slice: does the era yield enough clustering
-- material for pseudonym-graph matching, before paying to export one?
--
-- Three independent queries; run each on its own (bq query < this file will only take
-- the first). Two epochs of 144 blocks separated by seven epochs, the view separation
-- results/RESULTS-attribute-drift.md argues for (drift dips at multiples of 7).
--
-- Partition pruning is on block_timestamp_month and is NOT optional: filtering only on
-- block_number scans the whole table. Measured cost here is ~2.8-3.7 GB per query.
--
-- Block range caveat: the public dataset is missing 835 blocks above height 959194
-- (largest gap 962010-962489), so a slice must stay below that.

-- === 1. spanning material: how much survives from one view to the other ===
  SELECT
    IF(block_number <= 940112, 'A', 'B') AS epoch,
    `hash` AS txid,
    ARRAY(SELECT DISTINCT a FROM UNNEST(inputs) i, UNNEST(i.addresses) a) AS in_addr
  FROM `bigquery-public-data.crypto_bitcoin.transactions`
  WHERE block_timestamp_month = '2026-03-01'
    AND (block_number BETWEEN 939969 AND 940112
      OR block_number BETWEEN 940977 AND 941120)
    AND NOT is_coinbase
),
per_addr AS (
  SELECT epoch, a, COUNT(DISTINCT txid) AS n_txs
  FROM tx, UNNEST(in_addr) a GROUP BY epoch, a
),
a_side AS (SELECT a FROM per_addr WHERE epoch = 'A'),
b_side AS (SELECT a FROM per_addr WHERE epoch = 'B')
SELECT
  (SELECT COUNT(*) FROM tx WHERE epoch = 'A') AS txs_a,
  (SELECT COUNT(*) FROM tx WHERE epoch = 'B') AS txs_b,
  (SELECT COUNTIF(ARRAY_LENGTH(in_addr) >= 2) FROM tx WHERE epoch = 'A') AS cospend_txs_a,
  (SELECT COUNTIF(ARRAY_LENGTH(in_addr) >= 2) FROM tx WHERE epoch = 'B') AS cospend_txs_b,
  (SELECT COUNT(*) FROM a_side) AS in_addrs_a,
  (SELECT COUNT(*) FROM b_side) AS in_addrs_b,
  (SELECT COUNTIF(n_txs >= 2) FROM per_addr WHERE epoch = 'A') AS reused_addrs_a,
  (SELECT COUNT(*) FROM a_side JOIN b_side USING (a)) AS addrs_in_both

-- === 2. degree and cluster-material of the spanning addresses ===
  SELECT
    IF(block_number <= 940112, 'A', 'B') AS epoch,
    `hash` AS txid,
    ARRAY(SELECT DISTINCT a FROM UNNEST(inputs) i, UNNEST(i.addresses) a) AS in_addr,
    ARRAY(SELECT DISTINCT a FROM UNNEST(outputs) o, UNNEST(o.addresses) a) AS out_addr
  FROM `bigquery-public-data.crypto_bitcoin.transactions`
  WHERE block_timestamp_month = '2026-03-01'
    AND (block_number BETWEEN 939969 AND 940112
      OR block_number BETWEEN 940977 AND 941120)
    AND NOT is_coinbase
),
edge AS (
  SELECT epoch, i AS src, o AS dst, ARRAY_LENGTH(in_addr) AS n_in
  FROM tx, UNNEST(in_addr) i, UNNEST(out_addr) o
),
shared AS (
  SELECT src FROM edge WHERE epoch = 'A'
  INTERSECT DISTINCT
  SELECT src FROM edge WHERE epoch = 'B'
),
deg AS (
  SELECT e.epoch, e.src,
         COUNT(DISTINCT e.dst) AS out_degree,
         MAX(e.n_in) AS max_cospend
  FROM edge e JOIN shared s USING (src)
  GROUP BY e.epoch, e.src
)
SELECT epoch,
  COUNT(*) AS shared_addrs,
  COUNTIF(max_cospend >= 2) AS in_a_cospend,
  ROUND(AVG(out_degree), 2) AS mean_degree,
  APPROX_QUANTILES(out_degree, 100)[OFFSET(50)] AS p50_degree,
  APPROX_QUANTILES(out_degree, 100)[OFFSET(90)] AS p90_degree,
  COUNTIF(out_degree = 1) AS degree_1,
  COUNTIF(out_degree >= 3) AS degree_3plus
FROM deg GROUP BY epoch ORDER BY epoch

-- === 3. seed supply: is the high-degree population the same in both views? ===
  SELECT IF(block_number <= 940112, 'A', 'B') AS epoch, `hash` AS txid,
    ARRAY(SELECT DISTINCT a FROM UNNEST(inputs) i, UNNEST(i.addresses) a) AS in_addr,
    ARRAY(SELECT DISTINCT a FROM UNNEST(outputs) o, UNNEST(o.addresses) a) AS out_addr
  FROM `bigquery-public-data.crypto_bitcoin.transactions`
  WHERE block_timestamp_month = '2026-03-01'
    AND (block_number BETWEEN 939969 AND 940112
      OR block_number BETWEEN 940977 AND 941120)
    AND NOT is_coinbase
),
deg AS (
  SELECT epoch, i AS addr, COUNT(DISTINCT o) AS d
  FROM tx, UNNEST(in_addr) i, UNNEST(out_addr) o
  GROUP BY epoch, addr
),
ranked AS (
  SELECT epoch, addr, d, ROW_NUMBER() OVER (PARTITION BY epoch ORDER BY d DESC) AS rk
  FROM deg
),
paired AS (
  SELECT a.addr, a.rk AS rk_a, b.rk AS rk_b, a.d AS d_a, b.d AS d_b
  FROM (SELECT * FROM ranked WHERE epoch = 'A') a
  JOIN (SELECT * FROM ranked WHERE epoch = 'B') b USING (addr)
)
SELECT k,
  COUNTIF(rk_a <= k AND rk_b <= k) AS in_top_k_both,
  ROUND(COUNTIF(rk_a <= k AND rk_b <= k) / k, 3) AS precision_at_k,
  MIN(IF(rk_a <= k, d_a, NULL)) AS min_degree_at_k
FROM paired, UNNEST([50, 100, 200, 500, 1000, 5000]) AS k
GROUP BY k ORDER BY k
