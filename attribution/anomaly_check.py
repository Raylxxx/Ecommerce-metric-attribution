"""第 1 步：排除假异动。

三项检查（SQL 版本在 sql/04_attribution/01~03）：
1. 事件结构：只有某一个事件断崖、而它下游的事件没跟着变 → 大概率埋点丢失；
2. 小时分布：某个小时之后数据几乎为 0 → 数据延迟 / 任务没跑完；
3. 维度新值：某个取值只在一期出现且占比不小 → 口径或埋点变更。

另外加一项「显著性」：变化幅度落在历史周同比波动的 2 倍标准差以内，就判为正常波动，
避免对没有异动的日期硬找原因（评测集里专门放了 5 个无异动对照用例）。

判定顺序：先看 1~3 有没有数据问题，有就停下，不做业务归因；再看显著性。
"""

from __future__ import annotations

import math
import statistics
from typing import Mapping, Sequence

import pandas as pd

# 漏斗顺序，用来判断「下游事件有没有跟着变」
FUNNEL = [
    "page_view", "view_item", "add_to_cart", "begin_checkout",
    "add_shipping_info", "add_payment_info", "purchase",
]

MIN_EVENT_COUNT = 50         # 基准期事件数太少的不参与离群判断（另有计数 z 值兜底）
MIN_DOWNSTREAM_COUNT = 20    # 判断「下游有没有跟着变」时门槛放低，否则小切片里下游事件全被过滤掉
OUTLIER_FLOOR = 0.15         # 偏离中位数至少 15% 才算离群
OUTLIER_MAD_MULT = 3.0       # 偏离程度 > 其他事件典型偏离的 3 倍
COUNT_Z = 4.0                # 计数层面的 z 值阈值，排除小计数事件的随机波动
DOWNSTREAM_FOLLOW = 0.3      # 下游事件变化不到离群事件的 30%，视为「没跟着变」
TRUNC_RATIO = 0.05           # 当前期某小时量 < 基准期同小时的 5% 视为断掉
NEW_VALUE_MIN_SHARE = 0.01   # 新出现 / 消失的维度值占比 ≥ 1% 才报
SIGMA_MULT = 2.0             # 显著性：超过历史 WoW 波动 2 倍标准差
FACTOR_SIGMA_MULT = 3.0      # 因子级显著性阈值更严，控制误报
FALLBACK_THRESHOLD = 0.10    # 历史不够时用固定阈值 10%


def event_mix_check(cur_counts: Mapping[str, float], base_counts: Mapping[str, float],
                    min_count: int = MIN_EVENT_COUNT) -> dict:
    """事件结构对比。输入是两期各事件的计数 {event_name: cnt}。"""
    events = [e for e in base_counts if base_counts[e] >= min_count]
    chg = {e: cur_counts.get(e, 0) / base_counts[e] - 1 for e in events}
    if len(chg) < 3:
        return {"check": "event_mix", "flag": False, "changes": chg,
                "finding": "可比较的事件少于 3 个，跳过"}
    med = statistics.median(chg.values())
    dev = {e: abs(c - med) for e, c in chg.items()}
    typical = statistics.median(dev.values())
    thr = max(OUTLIER_MAD_MULT * typical, OUTLIER_FLOOR)
    # 计数本身有泊松噪音：基准期只有一两百次的事件，变化 20% 也可能是随机的。
    # 所以离群还要求计数层面的 z 值足够大（期望值按其他事件的中位数变化推算）
    def count_z(e):
        exp = base_counts[e] * (1 + med)
        return (cur_counts.get(e, 0) - exp) / math.sqrt(exp) if exp > 0 else 0.0

    outliers = [e for e, v in dev.items() if v > thr and abs(count_z(e)) > COUNT_Z]

    flag, suspect, reason = False, None, "各事件变化幅度一致，没有单一事件断崖"
    if len(outliers) == 1:
        e = outliers[0]
        chg_all = {x: cur_counts.get(x, 0) / base_counts[x] - 1
                   for x in base_counts if base_counts[x] >= MIN_DOWNSTREAM_COUNT}
        chg_all.update(chg)
        downstream = [x for x in FUNNEL[FUNNEL.index(e) + 1:] if x in chg_all] if e in FUNNEL else []
        # 「跟着变」要求方向一致：加购掉 70%、下单反而涨，说明用户其实还在走流程
        sign = 1 if chg[e] >= med else -1
        follows = [x for x in downstream if (chg_all[x] - med) * sign >= DOWNSTREAM_FOLLOW * dev[e]]
        if downstream and not follows:
            flag, suspect = True, e
            reason = (f"只有 {e} 变化 {chg[e]:+.1%}（其他事件中位数 {med:+.1%}），"
                      f"且下游 {', '.join(downstream)} 没有跟着变 → 疑似埋点丢失")
        elif not downstream:
            reason = f"{e} 单独变化 {chg[e]:+.1%}，但它是漏斗最后一步，无法仅凭结构判断为埋点问题"
        else:
            reason = f"{e} 变化 {chg[e]:+.1%}，下游 {', '.join(follows)} 同步变化 → 更像真实行为变化"
    elif len(outliers) > 1:
        reason = f"多个事件同时偏离（{', '.join(outliers)}），符合真实行为变化"
    return {"check": "event_mix", "flag": flag, "suspect_event": suspect,
            "changes": chg, "median_change": med, "outliers": outliers, "finding": reason}


def event_mix_by_slice(cur: pd.DataFrame, base: pd.DataFrame, slice_col: str = "os",
                       min_count: int = MIN_EVENT_COUNT) -> list[dict]:
    """分切片做事件结构检查。埋点问题经常只出现在某个端（例如只有 iOS 的加购不上报），
    全站汇总时会被稀释，所以我额外按 os 切一遍。cur / base 列：slice_col, event_name, cnt。"""
    res = []
    for v in sorted(set(base[slice_col]) | set(cur[slice_col])):
        b = base[base[slice_col] == v].set_index("event_name")["cnt"].to_dict()
        c = cur[cur[slice_col] == v].set_index("event_name")["cnt"].to_dict()
        r = event_mix_check(c, b, min_count)
        r["slice"] = {slice_col: v}
        res.append(r)
    return res


def hourly_truncation_check(cur_hourly: Mapping[int, float], base_hourly: Mapping[int, float],
                            ratio: float = TRUNC_RATIO) -> dict:
    """小时分布检查：找最早的小时 h，使得 h 之后每个小时当前期量都 < 基准期同小时的 5%。"""
    hours = list(range(24))
    trunc_at = None
    for h in hours:
        tail = [x for x in hours[h:] if base_hourly.get(x, 0) > 0]
        if not tail:
            break
        if all(cur_hourly.get(x, 0) < ratio * base_hourly[x] for x in tail):
            trunc_at = h
            break
    flag = trunc_at is not None and trunc_at > 0
    last_hour = max((h for h in hours if cur_hourly.get(h, 0) > 0), default=None)
    finding = (f"当前期 {trunc_at}:00 之后数据几乎为 0（最后有数据的小时 {last_hour}）→ 疑似数据延迟/截断"
               if flag else "小时分布完整，没有截断")
    return {"check": "hourly", "flag": flag, "truncated_from_hour": trunc_at,
            "last_hour_with_data": last_hour, "finding": finding}


def new_dim_values_check(cur: Mapping[str, float], base: Mapping[str, float], dim: str,
                         min_share: float = NEW_VALUE_MIN_SHARE) -> dict:
    """维度新值检查：只在一期出现、并且占比不小的取值。"""
    tc, tb = sum(cur.values()) or 1, sum(base.values()) or 1
    appeared = {k: v / tc for k, v in cur.items() if base.get(k, 0) == 0 and v / tc >= min_share}
    vanished = {k: v / tb for k, v in base.items() if cur.get(k, 0) == 0 and v / tb >= min_share}
    flag = bool(appeared or vanished)
    parts = []
    if appeared:
        parts.append("新出现：" + ", ".join(f"{k}({s:.1%})" for k, s in appeared.items()))
    if vanished:
        parts.append("消失：" + ", ".join(f"{k}({s:.1%})" for k, s in vanished.items()))
    return {"check": f"new_values_{dim}", "flag": flag, "appeared": appeared, "vanished": vanished,
            "finding": "；".join(parts) + " → 疑似口径/埋点变更" if flag else f"{dim} 取值没有新增或消失"}


def _z(pct: float, hist: Sequence[float]) -> float | None:
    hist = [x for x in hist if pd.notna(x)]
    if len(hist) < 8:
        return None
    sd = statistics.pstdev(hist)
    return (pct - statistics.mean(hist)) / sd if sd else float("inf")


def significance_check(cur_value: float, base_value: float,
                       history_wow: Sequence[float] | None = None,
                       factors: Mapping[str, tuple[float, float, Sequence[float]]] | None = None) -> dict:
    """显著性：当前期相对基准期的变化，和历史周同比波动比较。

    只看 GMV 不够：订单少的时候 GMV 自身噪音很大，访客数掉了三成也可能被淹没。
    所以我同时看 UV / CR / AOV 各自的周同比 z 值，因子的阈值更严（3 倍标准差），
    控制多重比较带来的误报。factors: {'uv': (cur, base, history_wow), ...}
    """
    pct = cur_value / base_value - 1 if base_value else float("inf")
    z = _z(pct, history_wow or [])
    if z is not None:
        significant = abs(z) > SIGMA_MULT
        rule = f"GMV |z|={abs(z):.2f}，阈值 {SIGMA_MULT}"
    else:
        significant = abs(pct) > FALLBACK_THRESHOLD
        rule = f"历史样本不足，GMV 用固定阈值 ±{FALLBACK_THRESHOLD:.0%}"

    factor_z = {}
    for f, (c, b, hist) in (factors or {}).items():
        fp = c / b - 1 if b else float("inf")
        fz = _z(fp, hist)
        factor_z[f] = {"pct_change": fp, "z": fz}
    hot = [f for f, v in factor_z.items() if v["z"] is not None and abs(v["z"]) > FACTOR_SIGMA_MULT]
    if hot and not significant:
        significant = True
        rule += f"；但因子 {', '.join(hot)} 的 |z| 超过 {FACTOR_SIGMA_MULT}"
    return {"check": "significance", "pct_change": pct, "z": z, "significant": significant,
            "factor_z": factor_z, "significant_factors": hot,
            "finding": f"GMV 变化 {pct:+.1%}，{rule} → {'显著' if significant else '在正常波动范围内'}"}


def judge(checks: Sequence[dict], significance: dict | None) -> dict:
    """汇总各项检查，给出最终判定。"""
    data_issues = [c for c in checks if c.get("flag")]
    if data_issues:
        kinds = []
        for c in data_issues:
            if c["check"].startswith("event_mix"):
                kinds.append("tracking_loss")
            elif c["check"] == "hourly":
                kinds.append("data_delay")
            else:
                kinds.append("definition_change")
        # 小时截断证据最硬，优先报
        kind = "data_delay" if "data_delay" in kinds else kinds[0]
        return {"verdict": "data_issue", "is_real_anomaly": False, "issue_type": kind,
                "confidence": "high" if len(data_issues) == 1 else "medium"}
    if significance is not None and not significance["significant"]:
        return {"verdict": "no_anomaly", "is_real_anomaly": False, "issue_type": None,
                "confidence": "medium"}
    return {"verdict": "real_anomaly", "is_real_anomaly": True, "issue_type": None,
            "confidence": "high" if significance and significance.get("z") is not None else "medium"}
