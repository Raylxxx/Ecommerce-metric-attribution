"""把四步法串成一条流水线（离线 / pandas 版）。

线上我是让 Claude Code 的三个 subagent 通过 MCP 查 BigQuery 来跑这四步；
这里是同一套规则的确定性实现，有两个用处：
1. 作为「规则基线」，评测时和 AI 助手的结论对比；
2. 生成 examples/demo_run/ 里的样例输出（01_check.json / 02_decompose.json / report.md）。

输出 JSON 的结构和 .claude/agents/*.md 里约定的结构保持一致。
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

from attribution import anomaly_check as ac
from attribution.drilldown import search_segments, additive_drilldown
from attribution.lmdi import lmdi_gmv, decompose_cr, decompose_aov
from attribution.metrics import daily_total, daily_by_dims, period_frame, row_of, map_top_countries

DIMS = ("channel", "device", "country")


def _counts(df: pd.DataFrame, dt, col: str) -> dict:
    sub = df[pd.to_datetime(df["event_dt"]) == pd.Timestamp(dt)]
    return sub.groupby(col).size().to_dict()


def _hourly(df: pd.DataFrame, dt) -> dict:
    sub = df[pd.to_datetime(df["event_dt"]) == pd.Timestamp(dt)]
    hrs = pd.to_datetime(sub["event_timestamp"], unit="us").dt.hour
    return hrs.value_counts().to_dict()


def run_checks(events: pd.DataFrame, cur_dt, base_dt, daily: pd.DataFrame | None = None) -> dict:
    """第 1 步：排除假异动。events 是清洗后的明细。"""
    daily = daily if daily is not None else daily_total(events)
    evidence = []

    ev = ac.event_mix_check(_counts(events, cur_dt, "event_name"), _counts(events, base_dt, "event_name"))
    evidence.append(ev)

    # 分 os 切片再查一遍事件结构，取第一个命中的切片作为证据
    def slice_counts(dt):
        sub = events[pd.to_datetime(events["event_dt"]) == pd.Timestamp(dt)]
        return sub.groupby(["os", "event_name"]).size().rename("cnt").reset_index()

    if "os" in events.columns:
        sliced = ac.event_mix_by_slice(slice_counts(cur_dt), slice_counts(base_dt), "os")
        hits = [s for s in sliced if s["flag"]]
        if hits:
            h = dict(hits[0])
            h["check"] = "event_mix_by_os"
            evidence.append(h)
        else:
            evidence.append({"check": "event_mix_by_os", "flag": False,
                             "finding": "按 os 切片后也没有发现单一事件断崖"})

    evidence.append(ac.hourly_truncation_check(_hourly(events, cur_dt), _hourly(events, base_dt)))
    for d in DIMS:
        evidence.append(ac.new_dim_values_check(_counts(events, cur_dt, d), _counts(events, base_dt, d), d))

    d = daily.copy()
    d["event_dt"] = pd.to_datetime(d["event_dt"])
    d = d.sort_values("event_dt").set_index("event_dt")

    def hist(col):
        wow = d[col] / d[col].shift(7) - 1
        return wow[wow.index < pd.Timestamp(base_dt)].dropna().tolist()

    cur_row, base_row = row_of(daily, cur_dt), row_of(daily, base_dt)
    factors = {f: (cur_row[f], base_row[f], hist(f)) for f in ("uv", "cr", "aov")}
    sig = ac.significance_check(cur_row["gmv"], base_row["gmv"], hist("gmv"), factors)
    verdict = ac.judge(evidence, sig)
    return {**verdict, "cur_dt": str(pd.Timestamp(cur_dt).date()), "base_dt": str(pd.Timestamp(base_dt).date()),
            "evidence": evidence, "significance": sig}


def pick_top_factor(contrib: dict, significant_factors: Sequence[str] | None) -> tuple[str, str]:
    """主导因子：优先在「自身变化显著」的因子里选贡献最大的。

    只按贡献绝对值选会被噪音带偏：订单少时 CR 的随机波动对 GMV 的贡献可能比真实的 UV 下降还大。
    """
    pool = [f for f in (significant_factors or []) if f in contrib]
    if pool:
        return max(pool, key=lambda f: abs(contrib[f])), "显著因子中贡献最大"
    return max(contrib, key=lambda f: abs(contrib[f])), "贡献绝对值最大"


def run_decompose(events: pd.DataFrame, cur_dt, base_dt, dims: Sequence[str] = DIMS,
                  daily: pd.DataFrame | None = None, significant_factors: Sequence[str] | None = None) -> dict:
    """第 2、3 步：LMDI 因子拆解 + 维度下钻。"""
    daily = daily if daily is not None else daily_total(events)
    b, c = row_of(daily, base_dt), row_of(daily, cur_dt)
    top = lmdi_gmv(b, c)
    top["top_factor"], factor_rule = pick_top_factor(top["contrib"], significant_factors)
    sub = None
    if top["top_factor"] == "cr":
        sub = decompose_cr(b, c)
    elif top["top_factor"] == "aov":
        sub = decompose_aov(b, c)

    # 下钻只需要两天的明细，先过滤掉其他日期，速度快很多
    two_days = events[pd.to_datetime(events["event_dt"]).isin([pd.Timestamp(cur_dt), pd.Timestamp(base_dt)])]
    by_dims = daily_by_dims(map_top_countries(two_days), dims)
    pf = period_frame(by_dims, cur_dt, base_dt)
    seg = search_segments(pf, top["top_factor"], dims)
    gmv_seg = additive_drilldown(pf, ["channel", "device"], "gmv")

    residual = sum(top["contrib"].values()) - top["delta"]
    return {
        "cur_dt": str(pd.Timestamp(cur_dt).date()),
        "base_dt": str(pd.Timestamp(base_dt).date()),
        "gmv0": top["gmv0"], "gmv1": top["gmv1"],
        "delta_gmv": top["delta"], "pct_change": top["pct_change"],
        "factors0": top["factors0"], "factors1": top["factors1"],
        "factor_change": top["factor_change"],
        "factor_contrib": top["contrib"], "factor_share": top["share"],
        "lmdi_residual": residual,
        "top_factor": top["top_factor"],
        "top_factor_rule": factor_rule,
        "sub_decompose": sub,
        "segment_search": seg,
        "top_segments": seg["top_segments"],
        "gmv_by_channel_device": [
            {"segment": {"channel": k[0], "device": k[1]}, **{c: float(v) for c, v in r.items()}}
            for k, r in gmv_seg.head(5).iterrows()
        ],
    }


def run_offline(events: pd.DataFrame, cur_dt, base_dt=None, dims: Sequence[str] = DIMS) -> dict:
    """完整四步。events 应该是清洗后的明细（metrics.clean_events 的输出）。"""
    cur_dt = pd.Timestamp(cur_dt)
    base_dt = pd.Timestamp(base_dt) if base_dt is not None else cur_dt - pd.Timedelta(days=7)
    daily = daily_total(events)
    check = run_checks(events, cur_dt, base_dt, daily)
    decompose = (run_decompose(events, cur_dt, base_dt, dims, daily,
                               check["significance"].get("significant_factors"))
                 if check["is_real_anomaly"] else None)
    return {"check": check, "decompose": decompose}
