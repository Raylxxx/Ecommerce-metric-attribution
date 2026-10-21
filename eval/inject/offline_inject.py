"""在 pandas 明细上做受控扰动（离线版注入）。

和 eval/inject/render_views.py 生成的 BigQuery 视图是同一套规则：
- 抽样用确定性哈希（case_id + user_pseudo_id），每次跑结果一致；
- 只改 case['date'] 当天的数据，基准期保持原样。

离线版的用处：在合成数据上验证「注入 → 规则基线 → 打分」这条链路是对的，
真正评测 AI 助手时用 BigQuery 上的视图。
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

CHECKOUT_AND_AFTER = ["begin_checkout", "add_shipping_info", "add_payment_info", "purchase"]


def _bucket(case_id: str, ids: pd.Series) -> np.ndarray:
    """0~99 的确定性分桶。BigQuery 那边用 FARM_FINGERPRINT，这里用 md5，抽样比例一致即可。"""
    uniq = ids.unique()
    m = {u: int(hashlib.md5(f"{case_id}{u}".encode()).hexdigest()[:8], 16) % 100 for u in uniq}
    return ids.map(m).to_numpy()


def _segment_mask(df: pd.DataFrame, seg: dict | None) -> pd.Series:
    m = pd.Series(True, index=df.index)
    for k, v in (seg or {}).items():
        m &= df[k] == v
    return m


def inject(events: pd.DataFrame, case: dict) -> pd.DataFrame:
    """按用例类型注入扰动，返回新的明细（不修改原表）。"""
    t = case["type"]
    if t == "control":
        return events
    pct = int(round((case.get("magnitude") or 0) * 100))
    day = pd.to_datetime(events["event_dt"]) == pd.Timestamp(case["date"])
    df = events

    if t == "traffic":
        # 该人群 X% 用户当天的全部事件消失
        m = day & _segment_mask(df, case["segment"])
        users = df.loc[m, "user_pseudo_id"]
        hit = pd.Series(_bucket(case["case_id"], users) < pct, index=users.index)
        return df.drop(hit[hit].index)

    if t == "conversion":
        # 该人群 X% 的买家，结算及之后的事件消失（模拟结算页故障）
        m = day & _segment_mask(df, case["segment"])
        buyers = df.loc[m & (df["event_name"] == "purchase"), "user_pseudo_id"].unique()
        b = pd.Series(buyers)
        affected = set(b[_bucket(case["case_id"], b) < pct]) if len(b) else set()
        drop = m & df["user_pseudo_id"].isin(affected) & df["event_name"].isin(CHECKOUT_AND_AFTER)
        return df[~drop]

    if t == "aov":
        # 该人群当天订单金额 × (1 − X%)
        m = day & _segment_mask(df, case["segment"]) & (df["event_name"] == "purchase")
        df = df.copy()
        df.loc[m, "revenue"] = df.loc[m, "revenue"] * (1 - case["magnitude"])
        return df

    if t == "tracking_loss":
        # 某个事件（可限定 os）X% 不上报，其他事件正常
        p = case["params"]
        m = day & (df["event_name"] == p["event"])
        if p.get("os"):
            m &= df["os"] == p["os"]
        # 按「用户 + 时间戳」逐条抽样，和 render_views.py 一致：丢的是部分上报，不是部分用户
        keys = df.loc[m, "user_pseudo_id"] + df.loc[m, "event_timestamp"].astype(str)
        hit = pd.Series(_bucket(case["case_id"], keys) < pct, index=keys.index)
        return df.drop(hit[hit].index)

    if t == "delay":
        # 当天 H 点之后的事件全部缺失
        h = case["params"]["hour"]
        hrs = pd.to_datetime(df["event_timestamp"], unit="us").dt.hour
        return df[~(day & (hrs >= h))]

    raise ValueError(f"未知用例类型：{t}")
