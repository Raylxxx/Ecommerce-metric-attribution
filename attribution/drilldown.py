"""维度下钻：在贡献最大的因子里找「哪个人群」变化最大。

两类指标分开处理：
- 可加指标（GMV、订单数、近似可加的 UV）：ΔY = Σ ΔY_i，直接按分组差值排序。
- 比率指标（CR、AOV）：总体比率 = Σ w_i · r_i，要拆成
      转化效应 Σ w̄_i · Δr_i   （人群自己变差了）
      结构效应 Σ r̄_i · Δw_i   （低转化人群占比变高了）
  w̄、r̄ 取两期平均，两项之和严格等于 Σ(w1·r1 − w0·r0)。

输入 DataFrame 统一是「长表」：dims + period(0=基准期, 1=当前期) + 指标列，
和 sql/04_attribution 里下钻 SQL 的输出列一致，方便直接把 BigQuery 结果喂进来。
"""

from __future__ import annotations

from typing import Sequence

import pandas as pd

# 只保留 UV 占比 ≥ 1% 的组合，防止小样本噪音把排名顶上去
DEFAULT_MIN_SHARE = 0.01
# 「集中」判定：Top1 ≥ 50% 或 Top3 ≥ 80%
TOP1_CONCENTRATED = 0.5
TOP3_CONCENTRATED = 0.8

# 每种因子对应的下钻方式：(类型, 分子, 分母)
FACTOR_SPEC = {
    "gmv": ("additive", "gmv", None),
    "uv": ("additive", "uv", None),
    "orders": ("additive", "orders", None),
    "cr": ("ratio", "orders", "uv"),
    "aov": ("ratio", "gmv", "orders"),
}


def _pivot(df: pd.DataFrame, dims: Sequence[str], cols: Sequence[str]) -> pd.DataFrame:
    g = df.groupby(list(dims) + ["period"])[list(cols)].sum().unstack("period").fillna(0)
    # 某一期完全没有数据时 unstack 会缺列，这里补齐
    for c in cols:
        for p in (0, 1):
            if (c, p) not in g.columns:
                g[(c, p)] = 0.0
    return g


def _weight_col(df: pd.DataFrame) -> str | None:
    return "uv" if "uv" in df.columns else None


def additive_drilldown(df: pd.DataFrame, dims: Sequence[str], value: str = "gmv",
                       min_share: float = DEFAULT_MIN_SHARE) -> pd.DataFrame:
    """可加指标下钻。返回每个组合的两期值、差值、占总变化比例，按 |差值| 降序。

    注意：UV 跨维度并不严格可加（同一用户一天内可能用两种设备），
    所以对 UV 用这个函数时，share_of_change 是近似值，报告里我会注明。
    """
    wcol = _weight_col(df)
    cols = [value] + ([wcol] if wcol and wcol != value else [])
    g = _pivot(df, dims, cols)
    out = pd.DataFrame({"v0": g[(value, 0)], "v1": g[(value, 1)]})
    out["delta"] = out["v1"] - out["v0"]
    if wcol:
        u = g[(wcol, 0)] + g[(wcol, 1)]
        out["uv_share"] = u / u.sum() if u.sum() else 0.0
    else:
        tot = out["v0"] + out["v1"]
        out["uv_share"] = tot / tot.sum() if tot.sum() else 0.0
    total = out["delta"].sum()
    out["share_of_change"] = out["delta"] / total if total else 0.0
    out["pct_change"] = (out["v1"] / out["v0"].where(out["v0"] != 0)) - 1
    out = out[out["uv_share"] >= min_share]
    return out.reindex(out["delta"].abs().sort_values(ascending=False).index)


def ratio_drilldown(df: pd.DataFrame, dims: Sequence[str], num: str, den: str,
                    min_share: float = DEFAULT_MIN_SHARE) -> pd.DataFrame:
    """比率指标下钻，拆转化效应（rate_effect）和结构效应（mix_effect）。

    权重 w 用分母的占比：CR 用 UV 占比，AOV 用订单占比。
    """
    wcol = _weight_col(df)
    cols = list(dict.fromkeys([num, den] + ([wcol] if wcol else [])))
    g = _pivot(df, dims, cols)
    d0, d1 = g[(den, 0)], g[(den, 1)]
    w0 = d0 / d0.sum() if d0.sum() else d0 * 0
    w1 = d1 / d1.sum() if d1.sum() else d1 * 0
    r0 = (g[(num, 0)] / d0.where(d0 != 0)).fillna(0.0)
    r1 = (g[(num, 1)] / d1.where(d1 != 0)).fillna(0.0)
    out = pd.DataFrame({
        "w0": w0, "w1": w1, "r0": r0, "r1": r1,
        "rate_effect": (w0 + w1) / 2 * (r1 - r0),
        "mix_effect": (r0 + r1) / 2 * (w1 - w0),
    })
    out["total_effect"] = out["rate_effect"] + out["mix_effect"]
    out["r_change"] = r1 - r0
    if wcol:
        u = g[(wcol, 0)] + g[(wcol, 1)]
        out["uv_share"] = u / u.sum() if u.sum() else 0.0
    else:
        out["uv_share"] = (w0 + w1) / 2
    # 分母为 0 的组合 ratio 用 0 填充，Σ 恒等式仍然成立（因为对应 w 也是 0）
    total = out["total_effect"].sum()
    out["share_of_change"] = out["total_effect"] / total if total else 0.0
    out = out[out["uv_share"] >= min_share]
    return out.reindex(out["total_effect"].abs().sort_values(ascending=False).index)


def cr_drilldown(df: pd.DataFrame, dims: Sequence[str] = ("channel", "device"),
                 min_share: float = DEFAULT_MIN_SHARE) -> pd.DataFrame:
    """转化率下钻。df 至少要有 dims + period + uv + orders。"""
    out = ratio_drilldown(df, dims, "orders", "uv", min_share)
    out["cr_change_pp"] = out["r_change"] * 100
    return out


def aov_drilldown(df: pd.DataFrame, dims: Sequence[str] = ("channel", "device"),
                  min_share: float = DEFAULT_MIN_SHARE) -> pd.DataFrame:
    """客单价下钻。df 至少要有 dims + period + orders + gmv。"""
    return ratio_drilldown(df, dims, "gmv", "orders", min_share)


def drilldown(df: pd.DataFrame, dims: Sequence[str], factor: str,
              min_share: float = DEFAULT_MIN_SHARE) -> pd.DataFrame:
    kind, num, den = FACTOR_SPEC[factor]
    if kind == "additive":
        return additive_drilldown(df, dims, num, min_share)
    return ratio_drilldown(df, dims, num, den, min_share)


def is_concentrated(shares: Sequence[float]) -> bool:
    """shares 已按贡献降序排好。Top1 ≥ 50% 或 Top3 ≥ 80% 视为集中。"""
    s = list(shares)
    if not s:
        return False
    return s[0] >= TOP1_CONCENTRATED or sum(s[:3]) >= TOP3_CONCENTRATED


def _top_records(t: pd.DataFrame, dims: Sequence[str], n: int = 5) -> list[dict]:
    t = t.sort_values("share_of_change", ascending=False).head(n).reset_index()
    recs = []
    for r in t.to_dict("records"):
        seg = {d: r.pop(d) for d in dims}
        recs.append({"segment": seg, **{k: (float(v) if pd.notna(v) else None) for k, v in r.items()}})
    return recs


def _top_uv_share(t: pd.DataFrame) -> float:
    if not len(t):
        return 0.0
    return float(t.loc[t["share_of_change"].idxmax(), "uv_share"])


def search_segments(df: pd.DataFrame, factor: str,
                    dims: Sequence[str] = ("channel", "device", "country"),
                    max_depth: int = 2, min_share: float = DEFAULT_MIN_SHARE,
                    keep_ratio: float = 0.8) -> dict:
    """组合搜索：单维度 → 选最集中的维度 → 与其他维度交叉，最多到 max_depth 维。

    往下一层的条件：新一层 Top1 贡献占比仍然「集中」，且不低于上一层 Top1 的 keep_ratio 倍。
    这样如果问题只在 mobile 整体，就不会硬拆到 mobile × 某个渠道。
    """
    levels = []

    def top1(t: pd.DataFrame) -> float:
        return float(t["share_of_change"].max()) if len(t) else 0.0

    # 第 1 层：每个维度各看一遍
    singles = {}
    for d in dims:
        t = drilldown(df, [d], factor, min_share)
        singles[d] = t
    best_dim = max(singles, key=lambda d: top1(singles[d]))
    best = {"dims": [best_dim], "table": singles[best_dim]}
    levels.append({
        "depth": 1,
        "by_dim": {d: _top_records(t, [d], 3) for d, t in singles.items()},
        "chosen_dims": [best_dim],
        "top1_share": top1(singles[best_dim]),
    })

    # 第 2 层及以上：在已选维度上逐个加维度
    while len(best["dims"]) < max_depth:
        cands = {}
        for d in dims:
            if d in best["dims"]:
                continue
            ds = best["dims"] + [d]
            cands[tuple(ds)] = drilldown(df, ds, factor, min_share)
        # 只考虑能真正把人群缩小的维度：如果加了一维以后 Top1 人群的 UV 占比几乎没变
        # （比如这个人群里只有一个国家），那这一维没有提供新信息
        parent_uv = _top_uv_share(best["table"])
        cands = {k: t for k, t in cands.items() if len(t) and _top_uv_share(t) <= 0.95 * parent_uv}
        if not cands:
            break
        ds_best = max(cands, key=lambda k: top1(cands[k]))
        t_best = cands[ds_best]
        prev = top1(best["table"])
        cur = top1(t_best)
        sorted_shares = t_best["share_of_change"].sort_values(ascending=False).tolist()
        accepted = is_concentrated(sorted_shares) and cur >= keep_ratio * prev
        levels.append({
            "depth": len(ds_best),
            "chosen_dims": list(ds_best),
            "top1_share": cur,
            "accepted": accepted,
            "top": _top_records(t_best, list(ds_best), 5),
        })
        if not accepted:
            break
        best = {"dims": list(ds_best), "table": t_best}

    final = _top_records(best["table"], best["dims"], 5)
    shares = best["table"]["share_of_change"].sort_values(ascending=False).tolist()
    return {
        "factor": factor,
        "dims": best["dims"],
        "top_segment": final[0]["segment"] if final else None,
        "top_segment_share": final[0]["share_of_change"] if final else None,
        "concentrated": is_concentrated(shares),
        "top_segments": final,
        "levels": levels,
    }
