import pandas as pd
import pytest

from attribution.drilldown import (additive_drilldown, aov_drilldown, cr_drilldown, is_concentrated,
                                   search_segments)


def _frame(rows):
    return pd.DataFrame(rows, columns=["channel", "device", "period", "uv", "orders", "gmv"])


@pytest.fixture
def mix_df():
    # 每个组合的 CR 两期都不变，只是低转化的 mobile 占比变高 → 只有结构效应
    return _frame([
        ("organic", "desktop", 0, 1000, 40, 2000), ("organic", "desktop", 1, 600, 24, 1200),
        ("organic", "mobile", 0, 1000, 10, 500), ("organic", "mobile", 1, 1400, 14, 700),
    ])


def test_cr_rate_plus_mix_equals_total_change(mix_df):
    out = cr_drilldown(mix_df, ("channel", "device"), min_share=0)
    cr0 = 50 / 2000
    cr1 = 38 / 2000
    assert out["total_effect"].sum() == pytest.approx(cr1 - cr0)
    assert out["rate_effect"].abs().sum() == pytest.approx(0)
    assert out["mix_effect"].sum() == pytest.approx(cr1 - cr0)


def test_rate_effect_only():
    df = _frame([
        ("organic", "desktop", 0, 1000, 40, 2000), ("organic", "desktop", 1, 1000, 20, 1000),
        ("organic", "mobile", 0, 1000, 10, 500), ("organic", "mobile", 1, 1000, 10, 500),
    ])
    out = cr_drilldown(df, ("channel", "device"), min_share=0)
    top = out.index[0]
    assert top == ("organic", "desktop")
    assert out.loc[top, "mix_effect"] == pytest.approx(0)
    assert out.loc[top, "cr_change_pp"] == pytest.approx(-2.0)


def test_additive_shares_sum_to_one(mix_df):
    out = additive_drilldown(mix_df, ["device"], "gmv", min_share=0)
    assert out["share_of_change"].sum() == pytest.approx(1.0)
    assert out["delta"].sum() == pytest.approx((1200 + 700) - (2000 + 500))


def test_aov_drilldown_identity():
    df = _frame([
        ("a", "desktop", 0, 1, 10, 500), ("a", "desktop", 1, 1, 10, 300),
        ("b", "mobile", 0, 1, 10, 400), ("b", "mobile", 1, 1, 20, 800),
    ])
    out = aov_drilldown(df, ("channel", "device"), min_share=0)
    assert out["total_effect"].sum() == pytest.approx(1100 / 30 - 900 / 20)


def test_min_share_filters_small_segments():
    df = _frame([
        ("big", "desktop", 0, 10000, 100, 5000), ("big", "desktop", 1, 10000, 90, 4500),
        ("tiny", "desktop", 0, 10, 5, 250), ("tiny", "desktop", 1, 10, 0, 0),
    ])
    out = cr_drilldown(df, ("channel", "device"), min_share=0.01)
    assert ("tiny", "desktop") not in out.index


def test_is_concentrated():
    assert is_concentrated([0.6, 0.2, 0.1])
    assert is_concentrated([0.4, 0.3, 0.2])
    assert not is_concentrated([0.3, 0.2, 0.2, 0.2])
    assert not is_concentrated([])


def test_search_goes_to_pair_when_problem_is_in_pair():
    rows = []
    for ch in ["organic", "cpc", "referral"]:
        for dev in ["desktop", "mobile"]:
            for p in (0, 1):
                uv = 1000
                orders = 30
                if p == 1 and (ch, dev) == ("organic", "mobile"):
                    orders = 10
                rows.append((ch, dev, p, uv, orders, orders * 50))
    seg = search_segments(_frame(rows).assign(country="US"), "cr", dims=("channel", "device", "country"))
    assert seg["top_segment"] == {"channel": "organic", "device": "mobile"} or \
        seg["top_segment"] == {"device": "mobile", "channel": "organic"}
    assert seg["concentrated"]


def test_search_stops_when_problem_is_whole_dimension():
    rows = []
    for ch in ["organic", "cpc", "referral"]:
        for dev in ["desktop", "mobile"]:
            for p in (0, 1):
                orders = 30 if not (p == 1 and dev == "mobile") else 15
                rows.append((ch, dev, p, 1000, orders, orders * 50))
    seg = search_segments(_frame(rows).assign(country="US"), "cr", dims=("channel", "device", "country"))
    assert seg["top_segment"] == {"device": "mobile"}
