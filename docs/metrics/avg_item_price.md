---
metric_id: avg_item_price
name_cn: 件单价
level: L3
parent: aov
children: []
unit: 美元 / 件
owner: 扬
updated: 待定稿
---

## 定义
GMV / 商品件数。

## 业务含义
AOV 的子因子之一：买的东西贵不贵。促销、折扣、品类结构变化会体现在这里。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(gmv), SUM(items)) AS avg_item_price
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆。

## 注意事项 / 常见错误
- 件单价下降不一定是降价，也可能是低价品类占比变高（结构效应）。

## 校验
件单价 × 商品件数 = GMV。
