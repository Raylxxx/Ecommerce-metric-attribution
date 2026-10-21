import math

import pytest

from attribution.lmdi import decompose_aov, decompose_cr, lmdi, lmdi_gmv, log_mean


def test_log_mean_basic():
    assert log_mean(5, 5) == 5
    assert log_mean(2, 1) == pytest.approx(1 / math.log(2))
    assert log_mean(1, 2) == log_mean(2, 1)


def test_log_mean_rejects_non_positive():
    with pytest.raises(ValueError):
        log_mean(0, 1)


def test_sum_equals_total():
    base = {"uv": 10000, "cr": 0.020, "aov": 50.0}   # 示例值
    cur = {"uv": 9500, "cr": 0.017, "aov": 48.0}     # 示例值
    r = lmdi(base, cur)
    assert sum(r["contrib"].values()) == pytest.approx(r["delta"], abs=1e-6)
    assert sum(r["share"].values()) == pytest.approx(1.0)


def test_cross_term_is_absorbed():
    # UV −10%、CR −10%：GMV 是 −19% 不是 −20%，LMDI 没有残差，两个因子各分一半
    r = lmdi({"uv": 100, "cr": 0.1, "aov": 10}, {"uv": 90, "cr": 0.09, "aov": 10})
    assert r["pct_change"] == pytest.approx(-0.19)
    assert r["contrib"]["uv"] == pytest.approx(r["contrib"]["cr"])
    assert r["contrib"]["aov"] == pytest.approx(0)


def test_single_factor_change_gets_all_credit():
    r = lmdi({"uv": 100, "cr": 0.1, "aov": 10}, {"uv": 100, "cr": 0.1, "aov": 8})
    assert r["share"]["aov"] == pytest.approx(1.0)


def _row(uv, view, cart, chk, buyer, orders, gmv, items):
    return dict(uv=uv, view_uv=view, cart_uv=cart, checkout_uv=chk, buyer_uv=buyer,
                orders=orders, gmv=gmv, items=items)


def test_lmdi_gmv_and_sub_decomposition_consistent():
    b = _row(5000, 2500, 750, 375, 200, 210, 10500, 380)
    c = _row(4800, 2450, 720, 300, 150, 155, 7600, 280)
    top = lmdi_gmv(b, c)
    assert top["gmv1"] - top["gmv0"] == pytest.approx(7600 - 10500)
    assert sum(top["contrib"].values()) == pytest.approx(top["delta"])
    cr = decompose_cr(b, c)
    assert sum(cr["contrib"].values()) == pytest.approx(top["contrib"]["cr"])
    aov = decompose_aov(b, c)
    assert sum(aov["contrib"].values()) == pytest.approx(top["contrib"]["aov"])
    assert top["factor_change"]["cr"] == pytest.approx((155 / 4800 - 210 / 5000) * 100)


def test_lmdi_gmv_zero_orders_raises():
    with pytest.raises(ValueError):
        lmdi_gmv(_row(100, 50, 10, 5, 0, 0, 0, 0), _row(100, 50, 10, 5, 1, 1, 10, 1))
