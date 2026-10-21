"""LMDI（对数平均迪氏指数法）因子拆解。

GMV = UV × CR × AOV 是乘法关系，直接把各因子变化率相加会留下交叉项残差。
LMDI 用对数平均 L(GMV1, GMV0) 做权重：

    ΔGMV_f = L(GMV1, GMV0) · ln(f1 / f0)

因为 ln(GMV1/GMV0) = Σ ln(f1/f0)，所以各因子贡献之和严格等于 GMV1 − GMV0，没有残差。
tests/test_lmdi.py 里专门测了这一点。
"""

from __future__ import annotations

import math
from typing import Iterable, Mapping

# 漏斗拆解用到的子因子：CR = 浏览率 × 加购率 × 结算率 × 下单完成率 × 人均订单数
CR_SUB_FACTORS = ("view_rate", "cart_rate", "checkout_rate", "completion_rate", "orders_per_buyer")
# AOV = 每单件数 × 件单价
AOV_SUB_FACTORS = ("items_per_order", "avg_item_price")


def log_mean(a: float, b: float) -> float:
    """对数平均 L(a, b)。a == b 时取极限值 a。"""
    if a <= 0 or b <= 0:
        raise ValueError(f"LMDI 要求各因子为正数，收到 a={a}, b={b}")
    if math.isclose(a, b, rel_tol=1e-12):
        return a
    return (a - b) / (math.log(a) - math.log(b))


def lmdi(base: Mapping[str, float], cur: Mapping[str, float],
         factors: Iterable[str] = ("uv", "cr", "aov")) -> dict:
    """对任意乘法恒等式 Y = Π f 做 LMDI 拆解。

    base / cur 是两期的因子取值，例如 {'uv': 1000, 'cr': 0.02, 'aov': 50}。
    返回：两期的 Y、总变化、每个因子的绝对贡献 contrib、占总变化的比例 share。
    """
    factors = tuple(factors)
    for f in factors:
        if base[f] <= 0 or cur[f] <= 0:
            raise ValueError(f"因子 {f} 必须为正数（base={base[f]}, cur={cur[f]}），"
                             "订单数为 0 的日期没法做乘法拆解，需要换对比期或换维度")
    y0 = math.prod(base[f] for f in factors)
    y1 = math.prod(cur[f] for f in factors)
    weight = log_mean(y1, y0)
    contrib = {f: weight * math.log(cur[f] / base[f]) for f in factors}
    delta = y1 - y0
    share = {f: (c / delta if delta else 0.0) for f, c in contrib.items()}
    return {
        "y0": y0,
        "y1": y1,
        "delta": delta,
        "pct_change": delta / y0,
        "weight": weight,
        "contrib": contrib,
        "share": share,
    }


def _gmv_factors(row: Mapping[str, float]) -> dict:
    """从汇总表的一行（uv / orders / gmv）算出三个因子。"""
    uv, orders, gmv = float(row["uv"]), float(row["orders"]), float(row["gmv"])
    if uv <= 0 or orders <= 0 or gmv <= 0:
        raise ValueError(f"uv/orders/gmv 必须为正数：{dict(uv=uv, orders=orders, gmv=gmv)}")
    return {"uv": uv, "cr": orders / uv, "aov": gmv / orders}


def lmdi_gmv(base_row: Mapping[str, float], cur_row: Mapping[str, float]) -> dict:
    """GMV 三因子拆解。输入是 ads_daily_total 的两行（只要 uv / orders / gmv 三列）。

    额外返回两期的因子值，报告里的「基准期 / 当前期 / 变化」三列直接用。
    """
    f0, f1 = _gmv_factors(base_row), _gmv_factors(cur_row)
    r = lmdi(f0, f1, ("uv", "cr", "aov"))
    r["gmv0"], r["gmv1"] = r["y0"], r["y1"]
    r["factors0"], r["factors1"] = f0, f1
    r["factor_change"] = {
        "uv": f1["uv"] / f0["uv"] - 1,
        "cr": (f1["cr"] - f0["cr"]) * 100,      # 转化率变化用 pp（百分点）表示
        "aov": f1["aov"] / f0["aov"] - 1,
    }
    r["top_factor"] = max(r["contrib"], key=lambda k: abs(r["contrib"][k]))
    return r


def cr_sub_factors(row: Mapping[str, float]) -> dict:
    """把 CR 拆成漏斗各环节。这个恒等式在代数上严格成立（分子分母逐级约掉）。"""
    uv, view, cart = float(row["uv"]), float(row["view_uv"]), float(row["cart_uv"])
    chk, buyer, orders = float(row["checkout_uv"]), float(row["buyer_uv"]), float(row["orders"])
    return {
        "view_rate": view / uv,
        "cart_rate": cart / view,
        "checkout_rate": chk / cart,
        "completion_rate": buyer / chk,
        "orders_per_buyer": orders / buyer,
    }


def aov_sub_factors(row: Mapping[str, float]) -> dict:
    orders, gmv, items = float(row["orders"]), float(row["gmv"]), float(row["items"])
    return {"items_per_order": items / orders, "avg_item_price": gmv / items}


def _sub_decompose(base_row, cur_row, sub_fn, parent: str) -> dict:
    """在 GMV 层面继续往下一层拆：子因子的贡献之和 = 父因子对 GMV 的贡献。

    做法是沿用同一个权重 L(GMV1, GMV0)，因为 ln(CR1/CR0) = Σ ln(sub1/sub0)。
    这样报告里能直接说「结算率下降让 GMV 少了 $X」。
    """
    top = lmdi_gmv(base_row, cur_row)
    s0, s1 = sub_fn(base_row), sub_fn(cur_row)
    for k in s0:
        if s0[k] <= 0 or s1[k] <= 0:
            raise ValueError(f"子因子 {k} 出现 0，无法继续拆解")
    contrib = {k: top["weight"] * math.log(s1[k] / s0[k]) for k in s0}
    parent_contrib = top["contrib"][parent]
    return {
        "parent": parent,
        "parent_contrib": parent_contrib,
        "sub0": s0,
        "sub1": s1,
        "contrib": contrib,
        "share_of_parent": {k: (v / parent_contrib if parent_contrib else 0.0) for k, v in contrib.items()},
        "top_sub_factor": max(contrib, key=lambda k: abs(contrib[k])),
    }


def decompose_cr(base_row, cur_row) -> dict:
    """CR → 漏斗环节，回答「转化掉在哪一步」。"""
    return _sub_decompose(base_row, cur_row, cr_sub_factors, "cr")


def decompose_aov(base_row, cur_row) -> dict:
    """AOV → 每单件数 × 件单价，回答「是买得少了还是买得便宜了」。"""
    return _sub_decompose(base_row, cur_row, aov_sub_factors, "aov")
