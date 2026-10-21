"""用 pandas 复刻 SQL 里的清洗规则和指标口径。

为什么要在 Python 里再写一遍：
1. 离线（没有 BigQuery）时能用合成数据把整套流程跑通，方便写单元测试；
2. 评测时需要一份「标准答案」数字，我用这里的函数在注入后的数据上计算，
   再交给裁判比对，不让裁判自己算。

口径和 sql/01_dwd/02_dwd_events_clean.sql、sql/03_ads/*.sql 保持一致，
改了一边必须改另一边（tests/test_metrics.py 会检查几条关键恒等式）。
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

DIRTY_VALUES = {"<Other>", "(data deleted)", "(not set)", ""}
INVALID_TXN = {"(not set)", ""}

# 汇总表的计数列，和 ads_daily_metrics 字段一一对应
COUNT_EVENTS = {
    "new_uv": "first_visit",
    "view_uv": "view_item",
    "cart_uv": "add_to_cart",
    "checkout_uv": "begin_checkout",
    "buyer_uv": "purchase",
}


def clean_events(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """对应 dwd_events_clean 的 4 条清洗规则，同时返回每条规则影响了多少行。

    1. user_pseudo_id + event_name + event_timestamp 相同只留一条；
    2. 下单事件按 transaction_id 去重留最早一条，没有订单号的剔除；
    3. 金额 ≤ 0 或为空的下单事件剔除；
    4. 维度脏值归为 unknown（不剔除，否则 UV 会偏少）。
    """
    stats = {"rows_in": int(len(df))}
    d = df.sort_values("event_timestamp", kind="stable")
    d = d.drop_duplicates(["user_pseudo_id", "event_name", "event_timestamp"])
    stats["dup_rows_removed"] = stats["rows_in"] - int(len(d))

    d = d.copy()
    for col in ("channel", "country", "device"):
        if col in d.columns:
            dirty = d[col].isna() | d[col].isin(DIRTY_VALUES)
            stats[f"{col}_unknown_rows"] = int(dirty.sum())
            d.loc[dirty, col] = "unknown"

    is_pur = d["event_name"] == "purchase"
    pur = d[is_pur]
    no_txn = pur["transaction_id"].isna() | pur["transaction_id"].isin(INVALID_TXN)
    bad_rev = pur["revenue"].isna() | (pur["revenue"] <= 0)
    stats["purchase_no_txn_removed"] = int(no_txn.sum())
    stats["purchase_bad_revenue_removed"] = int((bad_rev & ~no_txn).sum())
    pur = pur[~no_txn & ~bad_rev]
    before = len(pur)
    pur = pur.drop_duplicates("transaction_id", keep="first")
    stats["purchase_dup_txn_removed"] = int(before - len(pur))

    out = pd.concat([d[~is_pur], pur], ignore_index=True)
    stats["rows_out"] = int(len(out))
    return out, stats


def _agg(df: pd.DataFrame, keys: Sequence[str]) -> pd.DataFrame:
    keys = list(keys)
    g = df.groupby(keys)
    res = pd.DataFrame({"uv": g["user_pseudo_id"].nunique()})
    for col, ev in COUNT_EVENTS.items():
        sub = df[df["event_name"] == ev]
        res[col] = sub.groupby(keys)["user_pseudo_id"].nunique()
    pur = df[df["event_name"] == "purchase"]
    pg = pur.groupby(keys)
    res["orders"] = pg["transaction_id"].nunique()
    res["gmv"] = pg["revenue"].sum()
    res["items"] = pg["item_qty"].sum()
    return res.fillna(0).reset_index()


def add_ratios(t: pd.DataFrame) -> pd.DataFrame:
    """在汇总表上补上 12 个指标里的比率类指标。分母为 0 时给 NaN，不硬填 0。"""
    t = t.copy()

    def div(a, b):
        return t[a] / t[b].where(t[b] != 0)

    t["cr"] = div("orders", "uv")
    t["aov"] = div("gmv", "orders")
    t["new_uv_ratio"] = div("new_uv", "uv")
    t["view_rate"] = div("view_uv", "uv")
    t["cart_rate"] = div("cart_uv", "view_uv")
    t["checkout_rate"] = div("checkout_uv", "cart_uv")
    t["completion_rate"] = div("buyer_uv", "checkout_uv")
    t["items_per_order"] = div("items", "orders")
    t["avg_item_price"] = div("gmv", "items")
    return t


def daily_total(df: pd.DataFrame) -> pd.DataFrame:
    """对应 ads_daily_total：只按日汇总，总体指标都从这张表取（UV 不可跨维度相加）。"""
    return add_ratios(_agg(df, ["event_dt"]))


def daily_by_dims(df: pd.DataFrame, dims: Sequence[str] = ("channel", "device", "country")) -> pd.DataFrame:
    """对应 ads_daily_metrics：日 × 维度。"""
    return _agg(df, ["event_dt", *dims])


def period_frame(daily_dims: pd.DataFrame, cur_dt, base_dt) -> pd.DataFrame:
    """把两天的数据整理成下钻函数要的长表：period=0 基准期，period=1 当前期。"""
    cur_dt, base_dt = pd.Timestamp(cur_dt), pd.Timestamp(base_dt)
    dt = pd.to_datetime(daily_dims["event_dt"])
    sub = daily_dims[dt.isin([cur_dt, base_dt])].copy()
    sub["period"] = (pd.to_datetime(sub["event_dt"]) == cur_dt).astype(int)
    return sub


def row_of(daily: pd.DataFrame, dt) -> dict:
    hit = daily[pd.to_datetime(daily["event_dt"]) == pd.Timestamp(dt)]
    if hit.empty:
        raise KeyError(f"汇总表里没有日期 {dt}")
    return hit.iloc[0].to_dict()


def map_top_countries(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """对应 sql/03_ads/01_top_countries.sql：按 UV 取前 n 个国家，其余归为 other。"""
    known = df[df["country"] != "unknown"]
    top = (known.groupby("country")["user_pseudo_id"].nunique()
             .sort_values(ascending=False).head(n).index)
    df = df.copy()
    df["country"] = df["country"].where(df["country"].isin(top), "other")
    return df
