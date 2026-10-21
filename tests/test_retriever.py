from pathlib import Path

import pytest

from eval.inject.generate_cases import read_jsonl
from eval.retrieval_eval import evaluate
from mcp_server.retriever import MetricDocRetriever, tokenize

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def retriever():
    return MetricDocRetriever(ROOT / "docs" / "metrics")


def test_all_12_metrics_loaded(retriever):
    assert len(retriever.docs) == 12
    for mid, meta in retriever.meta.items():
        assert meta.get("name_cn"), mid


def test_every_doc_has_required_sections():
    for p in (ROOT / "docs" / "metrics").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        for sec in ["## 定义", "## 计算 SQL", "## 可拆分维度", "## 注意事项 / 常见错误", "## 校验"]:
            assert sec in text, f"{p.name} 缺少 {sec}"


def test_tokenize_mixed():
    toks = tokenize("GMV 转化率")
    assert "gmv" in toks and "转化" in toks and "化率" in toks


def test_pitfall_section_ranked_first(retriever):
    hit = retriever.search_chunks("转化率 常见错误", 1)[0]
    assert hit["metric_id"] == "conversion_rate"
    assert "常见错误" in hit["section"]


def test_aov_not_confused_with_item_price(retriever):
    assert retriever.search_metric_ids("客单价下降", 1) == ["aov"]


def test_get_unknown_metric(retriever):
    assert "未找到" in retriever.get("nope")


def test_retrieval_hit_rate(retriever):
    res = evaluate(retriever, read_jsonl(ROOT / "eval" / "cases" / "retrieval_queries.jsonl"))
    assert res["hit@3"] >= 0.9
    assert res["hit@1"] >= 0.8
