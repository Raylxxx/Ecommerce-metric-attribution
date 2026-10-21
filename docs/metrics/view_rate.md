---
metric_id: view_rate
name_cn: 商品浏览率
level: L3
parent: conversion_rate
children: []
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
触发 `view_item` 的用户数 / UV。

## 业务含义
漏斗第一步：来的人有没有看商品。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(view_uv), SUM(uv)) AS view_rate
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆。

## 注意事项 / 常见错误
- 漏斗率按「用户是否触发过该事件」计算，不强制事件先后顺序（埋点评审发现有买家没有结算事件）。
- 如果只有 view_item 断崖式下降、下游加购下单正常，先怀疑埋点丢失。

## 校验
view_uv ≤ uv。
