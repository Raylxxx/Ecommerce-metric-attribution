-- 连通性测试：确认能访问 GA4 公共数据集，顺便记下事件数、用户数（写进 README 的「数据」一节）
-- 实测结果：events = 待实测，users = 待实测
SELECT
  COUNT(*)                       AS events,
  COUNT(DISTINCT user_pseudo_id) AS users
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131';
