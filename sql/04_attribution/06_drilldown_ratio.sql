-- 第 3 步 方法 B：比率指标（这里是 CR）拆转化效应和结构效应
-- 总体 CR = Σ w_i · cr_i，w_i = 分组 UV 占比
-- 转化效应 = Σ w̄_i · Δcr_i，结构效应 = Σ c̄r_i · Δw_i，两项之和 = Σ(w1·cr1 − w0·cr0)
-- 想看 AOV 就把 orders→gmv、uv→orders 替换掉；想换维度改 GROUP BY 即可
-- Python 版：attribution/drilldown.py::ratio_drilldown
WITH g AS (
  SELECT channel, device,
    SUM(IF(event_dt = @base_dt, uv, 0))     AS uv0,
    SUM(IF(event_dt = @cur_dt,  uv, 0))     AS uv1,
    SUM(IF(event_dt = @base_dt, orders, 0)) AS o0,
    SUM(IF(event_dt = @cur_dt,  orders, 0)) AS o1
  FROM `${PROJECT}.${DATASET}.ads_daily_metrics`
  WHERE event_dt IN (@base_dt, @cur_dt)
  GROUP BY 1, 2
), w AS (
  SELECT *,
    uv0 / SUM(uv0) OVER () AS w0,
    uv1 / SUM(uv1) OVER () AS w1,
    IFNULL(SAFE_DIVIDE(o0, uv0), 0) AS cr0,
    IFNULL(SAFE_DIVIDE(o1, uv1), 0) AS cr1,
    (uv0 + uv1) / SUM(uv0 + uv1) OVER () AS uv_share
  FROM g
), e AS (
  SELECT *,
    (w0 + w1) / 2 * (cr1 - cr0) AS rate_effect,
    (cr0 + cr1) / 2 * (w1 - w0) AS mix_effect
  FROM w
  WHERE (uv0 + uv1) > 0
)
SELECT channel, device, uv_share, w0, w1, cr0, cr1,
  (cr1 - cr0) * 100                 AS cr_change_pp,
  rate_effect, mix_effect,
  rate_effect + mix_effect          AS total_effect,
  SAFE_DIVIDE(rate_effect + mix_effect, SUM(rate_effect + mix_effect) OVER ()) AS share_of_change
FROM e
WHERE uv_share >= 0.01            -- 只保留 UV 占比 ≥ 1% 的组合
ORDER BY ABS(rate_effect + mix_effect) DESC
LIMIT 10;
