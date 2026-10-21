-- 清洗表 dwd_events_clean，规则来自埋点评审（docs/tracking_review.md）：
-- 1. user_pseudo_id + event_name + event_timestamp 相同只保留一条
-- 2. 下单事件按 transaction_id 去重保留最早一条；没有订单号的下单事件剔除
-- 3. 金额 <= 0 或为空的下单事件剔除
-- 4. 维度脏值统一归为 unknown（不剔除，否则 UV 偏少）
-- Python 侧对应 attribution/metrics.py::clean_events，两边规则要同步改
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.dwd_events_clean`
PARTITION BY event_dt AS
WITH dedup AS (
  SELECT * EXCEPT(rn) FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY user_pseudo_id, event_name, event_timestamp
      ORDER BY event_timestamp) AS rn
    FROM `${PROJECT}.${DATASET}.dwd_events`)
  WHERE rn = 1
),
norm AS (
  SELECT * REPLACE(
    IF(channel IN ('<Other>', '(data deleted)', '(not set)', '') OR channel IS NULL, 'unknown', channel) AS channel,
    IF(country IN ('<Other>', '(data deleted)', '(not set)', '') OR country IS NULL, 'unknown', country) AS country,
    IFNULL(device, 'unknown') AS device)
  FROM dedup
)
SELECT * FROM norm WHERE event_name != 'purchase'
UNION ALL
SELECT * EXCEPT(rn) FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY event_timestamp) AS rn
  FROM norm
  WHERE event_name = 'purchase'
    AND transaction_id IS NOT NULL AND transaction_id NOT IN ('(not set)', '')
    AND revenue > 0)
WHERE rn = 1;
