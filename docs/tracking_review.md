# 埋点评审报告

> 状态：检查 SQL 已写好（`sql/02_dq_checks/`），**结果列等我在 BigQuery 上实测后填写**。
> 跑法：`python scripts/run_sql.py sql/02_dq_checks/01_event_missing.sql -o docs/dq/01_event_missing.csv`，其余同理。

## 数据集说明

- 来源：`bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`，2020-11-01 ~ 2021-01-31（92 天）
- 规模：事件数 待实测，用户数 待实测（`sql/01_dwd/00_smoke_test.sql`）
- 这是官方 **混淆版** 样本：部分值显示为 `<Other>`、`(data deleted)`、`(not set)`，有些数据内部不完全一致。
  这本身就是评审素材，我在下面逐条记录，不当作没看到。
- 渠道口径：`traffic_source.medium` 是用户 **首次获客** 媒介，不是本次会话渠道。

## 五项检查

| # | 检查项 | 检查 SQL | 结果（实测） | 结论 | 处理规则 |
|---|---|---|---|---|---|
| 1 | 事件缺失 | `01_event_missing.sql` | 待实测（例：X 月 X 日 add_to_cart 偏离 X%） | 待判断：业务波动 / 疑似丢失 | 疑似丢失的日期标记为数据异常日，不参与案例选择 |
| 2 | 重复上报 | `02_duplicate_events.sql` | 待实测（各事件重复行数及占比） | — | 按 user + event + timestamp 去重 |
| 3 | 订单号一致性 | `03_purchase_txn_consistency.sql` | 待实测（无订单号比例、重复订单比例、金额异常数） | — | 无订单号剔除；按订单号去重留最早一条；金额 ≤ 0 剔除 |
| 4 | 漏斗顺序 | `04_funnel_order.sql` | 待实测（无结算事件的买家占比） | — | 漏斗率按「用户是否触发」计算，不强制顺序 |
| 5 | 维度脏值 | `05_dirty_dim_values.sql` | 待实测（channel / country 的 unknown 占比） | — | 统一归为 unknown，不剔除 |

## 清洗影响

| 项目 | 清洗前 | 清洗后 | 变化 |
|---|---|---|---|
| 事件行数 | 待实测 | 待实测 | |
| 下单事件数 | 待实测 | 待实测 | |
| GMV | 待实测 | 待实测 | |

（`sql/01_dwd/03_clean_stats.sql`）

## 对下游分析的影响

- 订单号缺失的下单事件被剔除后，GMV 会比 GA4 界面上的数字略低，这是有意为之：没有订单号就没法去重。
- 漏斗按「是否触发」统计，下单完成率可能 > 100%，口径文档里已注明。
- unknown 维度单独成组，下钻时如果 unknown 组贡献很大，要先回到这份评审判断是不是数据问题。
