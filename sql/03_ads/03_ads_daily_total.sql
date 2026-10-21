-- 汇总表 ads_daily_total：只按日，总体 UV / CR / AOV 一律从这张表取
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.ads_daily_total`
PARTITION BY event_dt AS
SELECT
  event_dt,
  COUNT(DISTINCT user_pseudo_id)                                          AS uv,
  COUNT(DISTINCT IF(event_name = 'first_visit',    user_pseudo_id, NULL)) AS new_uv,
  COUNT(DISTINCT IF(event_name = 'view_item',      user_pseudo_id, NULL)) AS view_uv,
  COUNT(DISTINCT IF(event_name = 'add_to_cart',    user_pseudo_id, NULL)) AS cart_uv,
  COUNT(DISTINCT IF(event_name = 'begin_checkout', user_pseudo_id, NULL)) AS checkout_uv,
  COUNT(DISTINCT IF(event_name = 'purchase',       user_pseudo_id, NULL)) AS buyer_uv,
  COUNT(DISTINCT IF(event_name = 'purchase',       transaction_id, NULL)) AS orders,
  SUM(IF(event_name = 'purchase', revenue, 0))                            AS gmv,
  SUM(IF(event_name = 'purchase', item_qty, 0))                           AS items,
  SAFE_DIVIDE(COUNT(DISTINCT IF(event_name = 'purchase', transaction_id, NULL)),
              COUNT(DISTINCT user_pseudo_id))                             AS cr,
  SAFE_DIVIDE(SUM(IF(event_name = 'purchase', revenue, 0)),
              COUNT(DISTINCT IF(event_name = 'purchase', transaction_id, NULL))) AS aov
FROM `${PROJECT}.${DATASET}.dwd_events_clean`
GROUP BY event_dt;
