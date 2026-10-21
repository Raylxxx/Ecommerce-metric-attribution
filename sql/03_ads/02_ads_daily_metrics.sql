-- 汇总表 ads_daily_metrics：日 × 渠道 × 设备 × 国家
-- 注意：UV 类字段跨维度不可加（同一用户一天内可能出现在两种设备），总体指标请用 ads_daily_total
-- GMV、订单数、件数是可加的
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.ads_daily_metrics`
PARTITION BY event_dt AS
WITH base AS (
  SELECT event_dt, channel, device,
    IF(country IN (SELECT country FROM `${PROJECT}.${DATASET}.top_countries`), country, 'other') AS country,
    user_pseudo_id, event_name, transaction_id, revenue, item_qty
  FROM `${PROJECT}.${DATASET}.dwd_events_clean`
)
SELECT
  event_dt, channel, device, country,
  COUNT(DISTINCT user_pseudo_id)                                          AS uv,
  COUNT(DISTINCT IF(event_name = 'first_visit',    user_pseudo_id, NULL)) AS new_uv,
  COUNT(DISTINCT IF(event_name = 'view_item',      user_pseudo_id, NULL)) AS view_uv,
  COUNT(DISTINCT IF(event_name = 'add_to_cart',    user_pseudo_id, NULL)) AS cart_uv,
  COUNT(DISTINCT IF(event_name = 'begin_checkout', user_pseudo_id, NULL)) AS checkout_uv,
  COUNT(DISTINCT IF(event_name = 'purchase',       user_pseudo_id, NULL)) AS buyer_uv,
  COUNT(DISTINCT IF(event_name = 'purchase',       transaction_id, NULL)) AS orders,
  SUM(IF(event_name = 'purchase', revenue, 0))                            AS gmv,
  SUM(IF(event_name = 'purchase', item_qty, 0))                           AS items
FROM base
GROUP BY 1, 2, 3, 4;
