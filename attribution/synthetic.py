"""合成数据生成器。

字段和 sql/01_dwd/01_dwd_events.sql 落出来的 dwd_events 完全一致，
用途是：没有 GCP 账号、或者不想花 BigQuery 额度的时候，也能把
清洗 → 指标 → 排假 → LMDI → 下钻 → 报告 → 评测 这一整条链路在本地跑通。

注意：合成数据里的任何数字都 **不是** Google Merchandise Store 的真实结论，
只用于验证代码逻辑。真实分析一律以 BigQuery 上的查询结果为准。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

CHANNELS = ["organic", "cpc", "referral", "(none)", "affiliate"]
CHANNEL_P = [0.38, 0.12, 0.22, 0.23, 0.05]
DEVICES = ["desktop", "mobile", "tablet"]
DEVICE_P = [0.57, 0.40, 0.03]
COUNTRIES = ["United States", "India", "Canada", "United Kingdom", "France",
             "Spain", "Germany", "Taiwan", "Japan", "China", "Brazil", "Italy"]
COUNTRY_P = [0.43, 0.10, 0.08, 0.05, 0.04, 0.03, 0.03, 0.03, 0.03, 0.03, 0.02, 0.13]
OS_BY_DEVICE = {
    "desktop": (["Windows", "Macintosh", "Linux"], [0.6, 0.33, 0.07]),
    "mobile": (["iOS", "Android"], [0.55, 0.45]),
    "tablet": (["iOS", "Android"], [0.7, 0.3]),
}
# 漏斗各步的条件概率；移动端结算后完成率更低，这是我故意放进去的结构差异，
# 用来检验「结构效应」能不能被拆出来
P_VIEW, P_CART, P_CHECKOUT = 0.50, 0.30, 0.50
P_BUY = {"desktop": 0.62, "mobile": 0.45, "tablet": 0.50}
P_SHIPPING, P_PAYMENT = 0.85, 0.85


@dataclass
class SyntheticConfig:
    start: str = "2020-11-01"
    end: str = "2021-01-31"
    users_per_day: int = 5000
    seed: int = 42
    dirty: bool = True                     # 是否混入脏数据（重复上报、无订单号等）
    weekday_factor: tuple = (1.05, 1.08, 1.06, 1.02, 0.95, 0.88, 0.90)  # 周一 ~ 周日
    special_days: dict = field(default_factory=dict)  # {'2020-11-27': 1.6} 这类节日放大系数


def _day_events(rng: np.random.Generator, dt: pd.Timestamp, n: int, day_idx: int) -> pd.DataFrame:
    ch = rng.choice(CHANNELS, n, p=CHANNEL_P)
    dev = rng.choice(DEVICES, n, p=DEVICE_P)
    cty = rng.choice(COUNTRIES, n, p=COUNTRY_P)
    os_ = np.empty(n, dtype=object)
    for d, (names, p) in OS_BY_DEVICE.items():
        m = dev == d
        os_[m] = rng.choice(names, m.sum(), p=p)
    uid = np.array([f"u{day_idx:03d}{i:06d}" for i in range(n)])
    sid = rng.integers(1_600_000_000, 1_700_000_000, n)

    day_start = int(dt.value // 1000)  # 微秒
    start = day_start + rng.integers(0, 86_400 - 3_600, n) * 1_000_000

    is_new = rng.random(n) < 0.7
    view = rng.random(n) < P_VIEW
    cart = view & (rng.random(n) < P_CART)
    chk = cart & (rng.random(n) < P_CHECKOUT)
    ship = chk & (rng.random(n) < P_SHIPPING)
    pay = ship & (rng.random(n) < P_PAYMENT)
    p_buy = np.vectorize(P_BUY.get)(dev)
    buy = chk & (rng.random(n) < p_buy)

    qty = 1 + rng.poisson(0.8, n)
    price = np.round(rng.lognormal(mean=3.1, sigma=0.55, size=n), 2)
    revenue = np.round(qty * price, 2)

    base = {"user_pseudo_id": uid, "session_id": sid, "device": dev, "os": os_,
            "country": cty, "channel": ch}
    frames = []

    def emit(mask, name, step, extra=None):
        idx = np.flatnonzero(mask)
        if len(idx) == 0:
            return
        f = {k: v[idx] for k, v in base.items()}
        f["event_name"] = name
        f["event_timestamp"] = start[idx] + step * 30_000_000 + rng.integers(0, 29_000_000, len(idx))
        if extra:
            for k, v in extra.items():
                f[k] = v[idx]
        frames.append(pd.DataFrame(f))

    all_users = np.ones(n, dtype=bool)
    emit(is_new, "first_visit", 0)
    emit(all_users, "session_start", 0)
    # page_view 每人 1~N 次
    n_pv = 1 + rng.poisson(2.0, n)
    rep = np.repeat(np.arange(n), n_pv)
    pv = {k: v[rep] for k, v in base.items()}
    pv["event_name"] = "page_view"
    pv["event_timestamp"] = start[rep] + rng.integers(1, 300, len(rep)) * 1_000_000
    frames.append(pd.DataFrame(pv))
    emit(view, "view_item", 2)
    emit(cart, "add_to_cart", 3)
    emit(chk, "begin_checkout", 4)
    emit(ship, "add_shipping_info", 5)
    emit(pay, "add_payment_info", 6)
    txn = np.array([f"T{day_idx:03d}{i:06d}" for i in range(n)], dtype=object)
    emit(buy, "purchase", 7, {"transaction_id": txn, "revenue": revenue.astype(float),
                              "item_qty": qty.astype(float)})

    out = pd.concat(frames, ignore_index=True)
    out["event_dt"] = dt
    return out


def _add_dirty(rng: np.random.Generator, df: pd.DataFrame) -> pd.DataFrame:
    """按我在真实数据里看到的几类问题，各混一点进去，用来测清洗规则。"""
    dup = df.sample(frac=0.005, random_state=int(rng.integers(1 << 31)))
    df = pd.concat([df, dup], ignore_index=True)
    pur = df.index[df["event_name"] == "purchase"]
    # 同一订单重复上报
    redo = df.loc[rng.choice(pur, max(1, len(pur) // 100), replace=False)].copy()
    redo["event_timestamp"] += 5_000_000
    df = pd.concat([df, redo], ignore_index=True)
    # 无订单号 / 金额为 0 的下单事件
    pur = df.index[df["event_name"] == "purchase"]
    bad = rng.choice(pur, max(1, len(pur) // 100), replace=False)
    df.loc[bad[: len(bad) // 2], "transaction_id"] = "(not set)"
    df.loc[bad[len(bad) // 2:], "revenue"] = 0.0
    # 维度脏值
    m = rng.random(len(df)) < 0.02
    df.loc[m, "channel"] = "(data deleted)"
    m = rng.random(len(df)) < 0.01
    df.loc[m, "country"] = "(not set)"
    return df


def generate_events(cfg: SyntheticConfig | None = None) -> pd.DataFrame:
    """生成 dwd_events 结构的事件明细。"""
    cfg = cfg or SyntheticConfig()
    rng = np.random.default_rng(cfg.seed)
    days = pd.date_range(cfg.start, cfg.end, freq="D")
    frames = []
    for i, dt in enumerate(days):
        mult = cfg.weekday_factor[dt.weekday()] * cfg.special_days.get(dt.strftime("%Y-%m-%d"), 1.0)
        n = int(rng.poisson(cfg.users_per_day * mult))
        frames.append(_day_events(rng, dt, n, i))
    df = pd.concat(frames, ignore_index=True)
    for c in ("transaction_id",):
        df[c] = df[c].astype(object)
    if cfg.dirty:
        df = _add_dirty(rng, df)
    cols = ["event_dt", "event_timestamp", "event_name", "user_pseudo_id", "session_id",
            "device", "os", "country", "channel", "transaction_id", "revenue", "item_qty"]
    return df[cols].sort_values(["event_dt", "event_timestamp"], kind="stable").reset_index(drop=True)
