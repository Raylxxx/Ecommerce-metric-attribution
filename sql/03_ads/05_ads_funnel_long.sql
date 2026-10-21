-- 漏斗长表：Tableau 画漏斗用长表更方便
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.ads_funnel_long` AS
SELECT event_dt, channel, device, country, step.step_order, step.step_name, step.users
FROM `${PROJECT}.${DATASET}.ads_daily_metrics`,
UNNEST([
  STRUCT(1 AS step_order, '访问' AS step_name, uv AS users),
  STRUCT(2, '浏览商品', view_uv),
  STRUCT(3, '加购', cart_uv),
  STRUCT(4, '结算', checkout_uv),
  STRUCT(5, '下单', buyer_uv)
]) AS step;
