-- 第 2 步：LMDI 因子拆解，ΔGMV = UV 贡献 + CR 贡献 + AOV 贡献（无残差）
-- Python 版：attribution/lmdi.py::lmdi_gmv，两边结果应一致
WITH p AS (
  SELECT
    SUM(IF(event_dt = @base_dt, uv, 0))     AS uv0,
    SUM(IF(event_dt = @cur_dt,  uv, 0))     AS uv1,
    SUM(IF(event_dt = @base_dt, orders, 0)) AS o0,
    SUM(IF(event_dt = @cur_dt,  orders, 0)) AS o1,
    SUM(IF(event_dt = @base_dt, gmv, 0))    AS g0,
    SUM(IF(event_dt = @cur_dt,  gmv, 0))    AS g1
  FROM `${PROJECT}.${DATASET}.ads_daily_total`
  WHERE event_dt IN (@base_dt, @cur_dt)
), f AS (
  SELECT *,
    o0 / uv0 AS cr0, o1 / uv1 AS cr1, g0 / o0 AS aov0, g1 / o1 AS aov1,
    IF(g1 = g0, g1, (g1 - g0) / (LN(g1) - LN(g0))) AS L
  FROM p
)
SELECT
  g0, g1, g1 - g0                       AS delta_gmv,
  SAFE_DIVIDE(g1 - g0, g0)              AS pct_change,
  uv0, uv1, cr0, cr1, aov0, aov1,
  L * LN(uv1 / uv0)                     AS contrib_uv,
  L * LN(cr1 / cr0)                     AS contrib_cr,
  L * LN(aov1 / aov0)                   AS contrib_aov,
  L * LN(uv1 / uv0) + L * LN(cr1 / cr0) + L * LN(aov1 / aov0) - (g1 - g0) AS residual
FROM f;
