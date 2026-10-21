-- 按 UV 取前 10 个国家，其余归为 other（长尾国家样本太小，下钻时全是噪音）
CREATE OR REPLACE TABLE `${PROJECT}.${DATASET}.top_countries` AS
SELECT country
FROM `${PROJECT}.${DATASET}.dwd_events_clean`
WHERE country != 'unknown'
GROUP BY country
ORDER BY COUNT(DISTINCT user_pseudo_id) DESC
LIMIT 10;
