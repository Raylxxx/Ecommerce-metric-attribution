-- 检查 1：事件缺失。每日每事件量和前 7 日均值比，偏离超过 50% 标记
-- 结论要区分「真实业务波动」（如黑五，所有事件一起涨）和「疑似埋点丢失」（只有一个事件掉）
WITH d AS (
  SELECT event_dt, event_name, COUNT(*) AS cnt
  FROM `${PROJECT}.${DATASET}.dwd_events`
  GROUP BY 1, 2
),
w AS (
  SELECT *,
    AVG(cnt) OVER (PARTITION BY event_name ORDER BY event_dt
                   ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS avg_7d
  FROM d
)
SELECT *, SAFE_DIVIDE(cnt, avg_7d) - 1 AS dev
FROM w
WHERE ABS(SAFE_DIVIDE(cnt, avg_7d) - 1) > 0.5
ORDER BY event_dt, event_name;
