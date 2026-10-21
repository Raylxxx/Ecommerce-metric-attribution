---
metric_id: uv
name_cn: 访客数 UV
level: L2
parent: gmv
children: [new_user_ratio]
unit: 人
owner: 扬
updated: 待定稿
---

## 定义
当日去重 `user_pseudo_id` 数。

## 业务含义
衡量「来了多少人」，GMV = UV × CR × AOV 的第一个因子。

## 计算 SQL
```sql
SELECT event_dt, uv
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt;
```

## 可拆分维度
channel / device / country 可拆，但 **UV 跨维度不可加**：同一用户一天内可能用了两种设备，分组 UV 之和 ≥ 总 UV。

## 注意事项 / 常见错误
- 总体 UV 只能从 ads_daily_total 取，不能把 ads_daily_metrics 的 uv 加起来。
- 多天的 UV 也不能把每日 UV 相加（会重复计人），要回到明细表重新 COUNT DISTINCT。
- user_pseudo_id 是设备级匿名 ID，同一个人换设备会被算成两个访客。

## 校验
SUM(ads_daily_metrics.uv) ≥ ads_daily_total.uv，每天都应成立。
