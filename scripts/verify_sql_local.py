"""本地验证 SQL 口径：把 BigQuery SQL 转成 DuckDB 方言，在合成数据上跑，
再和 attribution/metrics.py 的 pandas 结果逐项对比。

这样不花 BigQuery 额度也能确认「SQL 版和 Python 版是同一个口径」。

    pip install duckdb sqlglot
    python scripts/verify_sql_local.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from attribution.lmdi import lmdi_gmv  # noqa: E402
from attribution.drilldown import cr_drilldown  # noqa: E402
from attribution.metrics import (  # noqa: E402
    clean_events, daily_by_dims, daily_total, map_top_countries, period_frame, row_of,
)
from attribution.synthetic import SyntheticConfig, generate_events  # noqa: E402
from scripts.sql_template import render  # noqa: E402

BUILD = [
    "sql/01_dwd/02_dwd_events_clean.sql",
    "sql/03_ads/01_top_countries.sql",
    "sql/03_ads/02_ads_daily_metrics.sql",
    "sql/03_ads/03_ads_daily_total.sql",
]


def to_duckdb(sql: str, params: dict | None = None) -> list[str]:
    import sqlglot

    sql = re.sub(r"`[\w-]+\.[\w-]+\.(\w+)`", r"\1", sql)          # 去掉 project.dataset 前缀
    sql = re.sub(r"PARTITION BY event_dt AS", "AS", sql)           # DuckDB 没有分区
    for k, v in (params or {}).items():
        sql = sql.replace(f"@{k}", f"DATE '{v}'")
    return [s for s in sqlglot.transpile(sql, read="bigquery", write="duckdb") if s.strip()]


def main() -> int:
    import duckdb

    raw = generate_events(SyntheticConfig(start="2020-12-01", end="2020-12-21", users_per_day=1500))
    con = duckdb.connect()
    raw2 = raw.copy()
    raw2["event_dt"] = raw2["event_dt"].dt.date
    con.register("raw_df", raw2)
    con.execute("CREATE TABLE dwd_events AS SELECT * FROM raw_df")

    for f in BUILD:
        for stmt in to_duckdb(render(ROOT / f, "p", "d")):
            con.execute(stmt)
        print(f"[ok] {f}")

    sql_total = con.execute("SELECT * FROM ads_daily_total ORDER BY event_dt").df()
    py_total = daily_total(clean_events(raw)[0])
    ok = True
    for col in ["uv", "view_uv", "cart_uv", "checkout_uv", "buyer_uv", "orders", "gmv", "items"]:
        diff = (sql_total[col].astype(float).to_numpy() - py_total[col].astype(float).to_numpy())
        bad = abs(diff).max()
        print(f"  ads_daily_total.{col:<12} 最大差异 {bad:.6f}")
        ok &= bad < 1e-6

    # GMV 可加性：分维度汇总的 GMV 合计 = 总表 GMV
    g1 = con.execute("SELECT SUM(gmv) FROM ads_daily_metrics").fetchone()[0]
    g2 = con.execute("SELECT SUM(gmv) FROM ads_daily_total").fetchone()[0]
    print(f"  GMV 对数：metrics={g1:.2f} total={g2:.2f}")
    ok &= abs(g1 - g2) < 1e-6

    cur, base = "2020-12-16", "2020-12-09"
    for stmt in to_duckdb(render(ROOT / "sql/04_attribution/04_lmdi.sql", "p", "d"),
                          {"cur_dt": cur, "base_dt": base}):
        r = con.execute(stmt).df().iloc[0]
    py = lmdi_gmv(row_of(py_total, base), row_of(py_total, cur))
    for f in ("uv", "cr", "aov"):
        d = abs(r[f"contrib_{f}"] - py["contrib"][f])
        print(f"  LMDI contrib_{f:<4} SQL={r[f'contrib_{f}']:.4f} Python={py['contrib'][f]:.4f}")
        ok &= d < 1e-6
    print(f"  LMDI 残差（SQL）{r['residual']:.2e}")

    # 比率下钻：SQL 方法 B 和 Python cr_drilldown 的 total_effect 对比
    for stmt in to_duckdb(render(ROOT / "sql/04_attribution/06_drilldown_ratio.sql", "p", "d"),
                          {"cur_dt": cur, "base_dt": base}):
        sq = con.execute(stmt).df()
    pf = period_frame(daily_by_dims(map_top_countries(clean_events(raw)[0])), cur, base)
    pyd = cr_drilldown(pf, ("channel", "device"))
    m = sq.merge(pyd.reset_index(), on=["channel", "device"], suffixes=("_sql", "_py"))
    d = (m["total_effect_sql"] - m["total_effect_py"]).abs().max()
    print(f"  CR 下钻 total_effect 最大差异 {d:.2e}（对比 {len(m)} 个组合）")
    ok &= d < 1e-9 and len(m) > 0
    print("全部一致 ✅" if ok else "存在差异 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
