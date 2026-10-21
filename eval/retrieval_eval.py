"""口径检索（RAG）的命中率评测：hit@1、hit@3、MRR。

问法写成业务方真实会问的样子（eval/cases/retrieval_queries.jsonl），
每次改分词、别名表或文档结构后跑一遍，防止检索悄悄变差。

    python eval/retrieval_eval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.inject.generate_cases import read_jsonl  # noqa: E402
from mcp_server.retriever import MetricDocRetriever  # noqa: E402


def evaluate(retriever: MetricDocRetriever, queries: list[dict], k: int = 3) -> dict:
    hit1 = hitk = mrr = 0.0
    misses = []
    for q in queries:
        ranked = retriever.search_metric_ids(q["query"], top_k=len(retriever.docs))
        rank = ranked.index(q["expected"]) + 1 if q["expected"] in ranked else None
        hit1 += rank == 1
        hitk += rank is not None and rank <= k
        mrr += 1 / rank if rank else 0
        if rank != 1:
            misses.append({"query": q["query"], "expected": q["expected"], "got": ranked[:3]})
    n = len(queries)
    return {"n": n, "hit@1": round(hit1 / n, 4), f"hit@{k}": round(hitk / n, 4),
            "mrr": round(mrr / n, 4), "misses": misses}


if __name__ == "__main__":
    r = MetricDocRetriever(ROOT / "docs" / "metrics")
    res = evaluate(r, read_jsonl(ROOT / "eval" / "cases" / "retrieval_queries.jsonl"))
    print(json.dumps(res, ensure_ascii=False, indent=2))
