from collections import Counter

import pandas as pd
import pytest

from attribution.metrics import daily_total
from attribution.pipeline import run_offline
from eval.agreement import cohen_kappa, stratified_sample
from eval.inject.generate_cases import make_cases
from eval.inject.offline_inject import inject
from eval.inject.render_views import render_case
from eval.scoring import score_root_cause, segment_match


def test_case_mix_is_50():
    cases = make_cases(["2020-12-02", "2020-12-09"])
    assert len(cases) == 50
    assert Counter(c["type"] for c in cases) == {"traffic": 10, "conversion": 10, "aov": 10,
                                                 "tracking_loss": 10, "delay": 5, "control": 5}
    assert make_cases(["2020-12-02"]) == make_cases(["2020-12-02"])   # 固定随机种子，可复现


def test_render_views_parse():
    sqlglot = pytest.importorskip("sqlglot")
    for c in make_cases(["2020-12-09"]):
        for s in render_case(c, "proj"):
            assert "${" not in s
            sqlglot.parse(s, read="bigquery")


def test_segment_match():
    assert segment_match({"device": "mobile"}, {"device": "mobile"}) == 1.0
    assert segment_match({"device": "mobile"}, {"device": "mobile", "channel": "organic"}) == 0.5
    assert segment_match({"device": "mobile", "channel": "organic"}, {"device": "mobile"}) == 0.5
    assert segment_match({"device": "mobile"}, {"device": "desktop"}) == 0.0


def test_kappa():
    assert cohen_kappa([2, 1, 0, 2], [2, 1, 0, 2]) == pytest.approx(1.0)
    assert cohen_kappa([2, 2, 0, 0], [2, 0, 2, 0]) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        cohen_kappa([1], [1, 2])


def test_stratified_sample_covers_all_types():
    cases = make_cases(["2020-12-09"])
    ids = stratified_sample(cases, 20)
    t = {c["case_id"]: c["type"] for c in cases}
    assert len(ids) == 20 and len({t[i] for i in ids}) == 6


def _case(t, **kw):
    base = {"case_id": f"t_{t}", "type": t, "date": "2020-12-10", "base_date": "2020-12-03",
            "segment": None, "magnitude": None, "params": {}}
    base.update(kw)
    exp_factor = {"traffic": "uv", "conversion": "cr", "aov": "aov"}.get(t)
    base["expected"] = {
        "verdict": "real_anomaly" if exp_factor else ("no_anomaly" if t == "control" else "data_issue"),
        "is_real_anomaly": bool(exp_factor),
        "issue_type": {"tracking_loss": "tracking_loss", "delay": "data_delay"}.get(t),
        "top_factor": exp_factor, "segment": base["segment"],
    }
    return base


def test_injection_changes_only_target_day(events):
    c = _case("traffic", segment={"device": "mobile"}, magnitude=0.5)
    inj = inject(events, c)
    before, after = daily_total(events).set_index("event_dt"), daily_total(inj).set_index("event_dt")
    changed = before.index[(before["uv"] != after["uv"])]
    assert list(changed) == [pd.Timestamp("2020-12-10")]


@pytest.mark.parametrize("case, expected_score", [
    (_case("delay", params={"hour": 17}), 2),
    (_case("tracking_loss", magnitude=0.7, params={"event": "add_to_cart", "os": None}), 2),
    (_case("traffic", segment={"device": "mobile"}, magnitude=0.6), 2),
    (_case("traffic", segment={"channel": "organic", "device": "desktop"}, magnitude=0.6), 2),
    (_case("aov", segment={"device": "desktop"}, magnitude=0.6), 2),
    (_case("control"), 2),
])
def test_rule_baseline_on_strong_cases(events, case, expected_score):
    res = run_offline(inject(events, case), case["date"], case["base_date"])
    sc = score_root_cause(case, res["check"], res["decompose"])
    assert sc["root_cause"] == expected_score, (sc, res["check"]["verdict"])
