from attribution import anomaly_check as ac

BASE = {"page_view": 20000, "view_item": 8000, "add_to_cart": 2400, "begin_checkout": 1200,
        "add_shipping_info": 1000, "add_payment_info": 850, "purchase": 700, "session_start": 6000}


def scale(d, k, **override):
    out = {e: v * k for e, v in d.items()}
    out.update(override)
    return out


def test_uniform_drop_is_not_tracking_issue():
    r = ac.event_mix_check(scale(BASE, 0.8), BASE)
    assert not r["flag"]


def test_single_event_cliff_with_normal_downstream_is_flagged():
    cur = scale(BASE, 1.0, add_to_cart=BASE["add_to_cart"] * 0.4)
    r = ac.event_mix_check(cur, BASE)
    assert r["flag"] and r["suspect_event"] == "add_to_cart"


def test_checkout_drop_with_downstream_following_is_real():
    cur = scale(BASE, 1.0, begin_checkout=840, add_shipping_info=700, add_payment_info=595, purchase=490)
    r = ac.event_mix_check(cur, BASE)
    assert not r["flag"]


def test_purchase_only_drop_is_not_flagged():
    r = ac.event_mix_check(scale(BASE, 1.0, purchase=350), BASE)
    assert not r["flag"]
    assert "最后一步" in r["finding"]


def test_hourly_truncation():
    base = {h: 1000 for h in range(24)}
    cur = {h: (950 if h < 18 else 3) for h in range(24)}
    r = ac.hourly_truncation_check(cur, base)
    assert r["flag"] and r["truncated_from_hour"] == 18
    assert not ac.hourly_truncation_check(base, base)["flag"]


def test_new_dim_values():
    r = ac.new_dim_values_check({"organic": 900, "(data deleted)": 300}, {"organic": 1000}, "channel")
    assert r["flag"] and "(data deleted)" in r["appeared"]
    assert not ac.new_dim_values_check({"a": 1}, {"a": 1}, "channel")["flag"]


def test_significance():
    hist = [0.02, -0.03, 0.05, -0.04, 0.01, 0.0, -0.02, 0.03, 0.04, -0.01]
    assert not ac.significance_check(102, 100, hist)["significant"]
    assert ac.significance_check(70, 100, hist)["significant"]
    assert ac.significance_check(85, 100, [])["significant"]    # 历史不足，用 ±10% 兜底


def test_judge_priority():
    flags = [{"check": "event_mix", "flag": True}, {"check": "hourly", "flag": True}]
    assert ac.judge(flags, None)["issue_type"] == "data_delay"
    assert ac.judge([], {"significant": False})["verdict"] == "no_anomaly"
    assert ac.judge([], {"significant": True, "z": 3})["verdict"] == "real_anomaly"
