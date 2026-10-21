-- 检查 2：重复上报。同一用户、同一事件、同一微秒时间戳出现多次
SELECT event_name, COUNT(*) AS dup_groups, SUM(n - 1) AS extra_rows
FROM (
  SELECT user_pseudo_id, event_name, event_timestamp, COUNT(*) AS n
  FROM `${PROJECT}.${DATASET}.dwd_events`
  GROUP BY 1, 2, 3
  HAVING n > 1
)
GROUP BY event_name
ORDER BY extra_rows DESC;
