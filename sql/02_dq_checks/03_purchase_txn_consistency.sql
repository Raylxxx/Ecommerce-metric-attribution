-- 检查 3：下单事件和订单号是否一致
-- purchase_events > distinct_txn → 同一订单多次上报；no_txn_id > 0 → 无法去重的下单事件
SELECT
  COUNT(*)                                              AS purchase_events,
  COUNTIF(transaction_id IS NULL
          OR transaction_id IN ('(not set)', ''))       AS no_txn_id,
  COUNT(DISTINCT transaction_id)                        AS distinct_txn,
  COUNTIF(revenue IS NULL OR revenue <= 0)              AS bad_revenue,
  SUM(IF(transaction_id IS NULL OR transaction_id IN ('(not set)', ''), revenue, 0)) AS revenue_without_txn
FROM `${PROJECT}.${DATASET}.dwd_events`
WHERE event_name = 'purchase';
