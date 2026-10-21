-- 检查 4：漏斗顺序异常。有下单但当天没有加购 / 结算事件
WITH u AS (
  SELECT event_dt, user_pseudo_id,
    COUNTIF(event_name = 'add_to_cart')    AS atc,
    COUNTIF(event_name = 'begin_checkout') AS chk,
    COUNTIF(event_name = 'purchase')       AS pur
  FROM `${PROJECT}.${DATASET}.dwd_events`
  GROUP BY 1, 2
)
SELECT
  COUNTIF(pur > 0)                                   AS buyers,
  COUNTIF(pur > 0 AND chk = 0)                       AS buy_without_checkout,
  COUNTIF(pur > 0 AND atc = 0)                       AS buy_without_cart,
  SAFE_DIVIDE(COUNTIF(pur > 0 AND chk = 0), COUNTIF(pur > 0)) AS pct_without_checkout
FROM u;
