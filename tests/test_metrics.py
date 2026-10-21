import pandas as pd
import pytest

from attribution.metrics import clean_events, daily_by_dims, daily_total, map_top_countries


def test_cleaning_rules(raw_events):
    clean, st = clean_events(raw_events)
    pur = clean[clean["event_name"] == "purchase"]
    assert pur["transaction_id"].is_unique
    assert (pur["revenue"] > 0).all()
    assert not pur["transaction_id"].isin(["(not set)", ""]).any()
    assert not clean.duplicated(["user_pseudo_id", "event_name", "event_timestamp"]).any()
    assert not clean["channel"].isin(["(data deleted)", "(not set)", "<Other>"]).any()
    assert st["dup_rows_removed"] > 0 and st["purchase_no_txn_removed"] > 0


def test_identity_uv_cr_aov(events):
    t = daily_total(events)
    rebuilt = t["uv"] * t["cr"] * t["aov"]
    assert (rebuilt - t["gmv"]).abs().max() < 1e-6


def test_gmv_additive_uv_not_less(events):
    t = daily_total(events).set_index("event_dt")
    d = daily_by_dims(map_top_countries(events)).groupby("event_dt").sum(numeric_only=True)
    assert (d["gmv"] - t["gmv"]).abs().max() < 1e-6
    assert (d["orders"] == t["orders"]).all()
    assert (d["uv"] >= t["uv"]).all()   # UV 跨维度不可加，只能 ≥


def test_top_countries_excludes_unknown(events):
    m = map_top_countries(events, n=3)
    assert m["country"].nunique() <= 4
    assert "unknown" not in set(m["country"]) - {"other"}


def test_funnel_ratios_in_range(events):
    t = daily_total(events)
    for col in ["view_rate", "cart_rate", "checkout_rate", "new_uv_ratio"]:
        assert t[col].between(0, 1).all(), col
    assert t["completion_rate"].gt(0).all()
    assert pd.api.types.is_datetime64_any_dtype(t["event_dt"])
