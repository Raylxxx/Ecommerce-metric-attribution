-- 第 2 步（下一层）：CR 拆到漏斗环节，各环节贡献之和 = CR 对 GMV 的贡献
-- CR = 浏览率 × 加购率 × 结算率 × 下单完成率 × 人均订单数
WITH p AS (
  SELECT
    SUM(IF(event_dt = @base_dt, gmv, 0)) AS g0,         SUM(IF(event_dt = @cur_dt, gmv, 0)) AS g1,
    SUM(IF(event_dt = @base_dt, uv, 0)) AS uv0,          SUM(IF(event_dt = @cur_dt, uv, 0)) AS uv1,
    SUM(IF(event_dt = @base_dt, view_uv, 0)) AS v0,      SUM(IF(event_dt = @cur_dt, view_uv, 0)) AS v1,
    SUM(IF(event_dt = @base_dt, cart_uv, 0)) AS c0,      SUM(IF(event_dt = @cur_dt, cart_uv, 0)) AS c1,
    SUM(IF(event_dt = @base_dt, checkout_uv, 0)) AS k0,  SUM(IF(event_dt = @cur_dt, checkout_uv, 0)) AS k1,
    SUM(IF(event_dt = @base_dt, buyer_uv, 0)) AS b0,     SUM(IF(event_dt = @cur_dt, buyer_uv, 0)) AS b1,
    SUM(IF(event_dt = @base_dt, orders, 0)) AS o0,       SUM(IF(event_dt = @cur_dt, orders, 0)) AS o1
  FROM `${PROJECT}.${DATASET}.ads_daily_total`
  WHERE event_dt IN (@base_dt, @cur_dt)
), f AS (
  SELECT *, IF(g1 = g0, g1, (g1 - g0) / (LN(g1) - LN(g0))) AS L FROM p
)
SELECT
  L * LN((v1 / uv1) / (v0 / uv0)) AS contrib_view_rate,
  L * LN((c1 / v1)  / (c0 / v0))  AS contrib_cart_rate,
  L * LN((k1 / c1)  / (k0 / c0))  AS contrib_checkout_rate,
  L * LN((b1 / k1)  / (b0 / k0))  AS contrib_completion_rate,
  L * LN((o1 / b1)  / (o0 / b0))  AS contrib_orders_per_buyer,
  L * LN((o1 / uv1) / (o0 / uv0)) AS contrib_cr_total
FROM f;
