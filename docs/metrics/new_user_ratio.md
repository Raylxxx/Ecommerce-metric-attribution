---
metric_id: new_user_ratio
name_cn: 新访客占比
level: L3
parent: uv
children: []
unit: 比例（%）
owner: 扬
updated: 待定稿
---

## 定义
当日触发 `first_visit` 的用户数 / 当日 UV。

## 业务含义
流量结构指标：UV 的变化是新客带来的还是老客带来的。

## 计算 SQL
```sql
SELECT event_dt, SAFE_DIVIDE(SUM(new_uv), SUM(uv)) AS new_user_ratio
FROM `${PROJECT}.${DATASET}.ads_daily_total`
WHERE event_dt BETWEEN @start_dt AND @end_dt
GROUP BY event_dt;
```

## 可拆分维度
channel / device / country 可拆。

## 注意事项 / 常见错误
- first_visit 是设备首次访问，清 cookie 或换浏览器会被算成新访客，数值会偏高。
- 新访客占比变化本身不进 LMDI 恒等式，只用来解释 UV 的变化。

## 校验
new_uv ≤ uv。
