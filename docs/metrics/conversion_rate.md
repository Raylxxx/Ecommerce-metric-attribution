---
metric_id: conversion_rate
name_cn: 下单转化率
level: L2
parent: gmv
children: [view_rate, add_to_cart_rate, checkout_rate, purchase_completion_rate]
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
当日订单数 / 当日访客数（UV）。本项目统一用「订单口径」，不用「下单用户数 / UV」。

## 业务含义
衡量「来的人买不买」。GMV = UV × CR × AOV 中的第二个因子。

## 计算 SQL
```sql
SELECT event_dt,
  SAFE_DIVIDE(SUM(orders), SUM(uv)) AS conversion_rate
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country（注意：分维度后 UV 之和 ≥ 总 UV。**总体 CR 必须用总表算，不能把分组 CR 简单平均**）。下钻时要拆转化效应和结构效应（sql/04_attribution/06_drilldown_ratio.sql）。

## 注意事项 / 常见错误
- 分母是 UV，不是会话数。
- 订单必须用清洗后去重的 transaction_id。
- 比较转化率变化用 pp（百分点），不要用 %。例：2.0% → 1.7% 是 −0.3pp。
- 不能用 AVG(分组 CR) 当总体 CR，低流量分组会被放大权重。
- 整体 CR 下降不一定是哪个人群变差，也可能是低转化人群占比变高（结构效应）。

## 校验
总体 CR × UV 应等于订单数（误差 < 0.1%）。
