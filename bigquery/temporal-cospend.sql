-- Temporal fingerprint on CO-SPEND entities (multi-address wallets), a cleaner owner labeling than
-- single reused addresses (bigquery/temporal.sql), which skew toward 24/7 services with flat
-- schedules. Two goals: (1) group addresses spent together (co-spend heuristic = same owner) so a
-- multi-address wallet is one entity; (2) cap the tx count to drop mega-services, keeping
-- individual-like wallets where a timezone/activity schedule could actually exist.
--
-- Co-spend approximation: entity = the lexicographically smallest input address of each tx (a
-- one-hop merge — every tx whose smallest input is the same address lands in one entity). This is
-- NOT full transitive union-find; a wallet that rotates which address is smallest will split. It
-- still merges far more than single-address reuse and biases toward multi-input (consolidating)
-- wallets. One month = one partition (~GB, under the free 1 TB/month quota).
--
-- After download, run: python3 -m decluster.broadcast temporal <export.json>
-- The number that matters is the MATCHED (band-width-matched) AUC. > ~0.6 = a real schedule
-- signal survives the concentration control; ~0.5 = still a null, like reused addresses.
WITH tx_entity AS (
  SELECT
    UNIX_SECONDS(t.block_timestamp) AS ts,
    (SELECT MIN(a) FROM UNNEST(t.inputs) AS i, UNNEST(i.addresses) AS a) AS entity
  FROM `bigquery-public-data.crypto_bitcoin.transactions` AS t
  WHERE t.block_timestamp >= TIMESTAMP('2024-01-01')
    AND t.block_timestamp <  TIMESTAMP('2024-02-01')          -- one month -> one partition
    AND NOT t.is_coinbase
)
SELECT
  entity AS addr,
  ARRAY_AGG(ts) AS times
FROM tx_entity
WHERE entity IS NOT NULL
GROUP BY entity
HAVING COUNT(*) BETWEEN 8 AND 200          -- >=8 for a schedule; <=200 drops mega-services
LIMIT 20000
