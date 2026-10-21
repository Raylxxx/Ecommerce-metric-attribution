# 案例 1：12 月节日高峰后 GMV 回落归因

> 状态：分析框架和 SQL 已就绪，**所有数字待在 BigQuery 上实测后填写**。日期区间先在看板上确认真实异动点再定，不预设结论。
> 人工做这个案例的耗时：待记录（这是「人工 vs AI 排查耗时」对比的基线）

## TL;DR
- 当前期 GMV 相比基准期 待实测（每天约 待实测 美元）。
- 主要原因：待实测（因子贡献占比）。
- 问题集中在：待实测（人群 / 漏斗环节）。建议：待定。

## 1. 背景与对比口径
- 想回答的问题：回落是「人少了」还是「不买了」？哪个人群掉得最多？
- 当前期：2020-12-28 ~ 2021-01-03；基准期：2020-12-14 ~ 2020-12-20
- 指标口径：docs/metrics/gmv.md、uv.md、conversion_rate.md、aov.md

## 2. 是否为真异动
| 检查 | SQL | 结果 | 结论 |
|---|---|---|---|
| 事件结构 | sql/01_event_mix.sql | 待实测 | |
| 事件结构（按 os） | sql/01b_event_mix_by_os.sql | 待实测 | |
| 小时分布 | sql/02_hourly_distribution.sql | 待实测 | |
| 维度新值 | sql/03_new_dim_values.sql | 待实测 | |

## 3. 因子拆解（LMDI）
| 因子 | 基准期 | 当前期 | 变化 | 对 GMV 贡献 | 贡献占比 |
|---|---|---|---|---|---|
| UV | | | | | |
| CR | | | pp | | |
| AOV | | | | | |
| 合计 | | | | ΔGMV | 100% |

### 3.1 下一层拆解
（CR → 浏览率 / 加购率 / 结算率 / 下单完成率 / 人均订单数，或 AOV → 每单件数 × 件单价）

## 4. 维度下钻
| 人群 | UV 占比 | 贡献占比 | 转化效应 | 结构效应 | 比率变化 |
|---|---|---|---|---|---|

## 5. 结论与建议
| 发现 | 建议 | 负责方 | 验证指标 / 恢复标准 |
|---|---|---|---|

## 6. 局限
- 渠道为首次获客渠道；数据为混淆样本；没有去年同期对照。
- 节后回落本身可能是正常季节性，结论要区分「整体季节性」和「超出整体降幅的人群」。

## 附录：复现
单日对比可以直接用参数化 SQL（区间对比时把 `event_dt = @cur_dt` 改成 `BETWEEN`）：
```bash
python scripts/run_sql.py sql/04_attribution/04_lmdi.sql --cur <当前期> --base <基准期> -o reports/case_01_post_holiday_drop/sql/04_lmdi.csv
python scripts/run_sql.py sql/04_attribution/06_drilldown_ratio.sql --cur <当前期> --base <基准期> -o reports/case_01_post_holiday_drop/sql/06_drilldown.csv
```
