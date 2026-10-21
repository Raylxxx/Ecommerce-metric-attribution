---
metric_id: checkout_rate
name_cn: 结算率
level: L3
parent: conversion_rate
children: []
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
触发 `begin_checkout` 的用户数 / 触发 `add_to_cart` 的用户数。

## 业务含义
漏斗第三步：加购的人有没有去结算。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(checkout_uv), SUM(cart_uv)) AS checkout_rate
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆。

## 注意事项 / 常见错误
- 分母是加购用户。
- 结算页改版、运费策略变化通常先反映在这个环节。

## 校验
checkout_uv 一般 ≤ cart_uv。
