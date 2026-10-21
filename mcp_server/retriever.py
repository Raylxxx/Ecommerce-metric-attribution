"""《指标口径文档》检索（轻量 RAG）。

知识库只有十几篇短文档，我没有上向量数据库：
英文 token + 中文二元组（bigram）+ BM25 打分，已经足够准，而且命中原因可解释。
之后文档多了（比如把历史分析报告也放进来），再换成 embedding 检索，search() 的接口不变。

除了整篇检索，我还按「## 小节」切块，这样问「转化率常见错误」时
能直接把「注意事项 / 常见错误」那一节排在前面，而不是整篇塞给模型。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

# 中文常用口语 → 指标 id 的别名表，用户问法和文档写法经常对不上，靠这个兜底
ALIASES = {
    "gmv": ["成交额", "销售额", "交易额", "营收", "收入", "卖了多少"],
    "uv": ["访客", "流量", "用户数", "人数", "来的人"],
    "orders": ["订单", "单量"],
    "conversion_rate": ["转化", "转化率", "cr", "买不买"],
    "aov": ["客单价", "客单", "平均订单金额"],
    "new_user_ratio": ["新客", "新用户", "新访客"],
    "view_rate": ["浏览率", "商品浏览"],
    "add_to_cart_rate": ["加购", "购物车"],
    "checkout_rate": ["结算", "结账"],
    "purchase_completion_rate": ["支付", "下单完成", "完成率"],
    "items_per_order": ["件数", "每单件数", "连带"],
    "avg_item_price": ["件单价", "商品单价", "商品价格"],
}

K1, B = 1.5, 0.75


def tokenize(text: str) -> list[str]:
    text = text.lower()
    en = re.findall(r"[a-z][a-z0-9_]+", text)
    toks = list(en)
    for seg in re.findall(r"[一-鿿]+", text):
        if len(seg) == 1:
            toks.append(seg)
        toks.extend(seg[i:i + 2] for i in range(len(seg) - 1))
    return toks


def _split_front_matter(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 4:]
    return meta, text


def _sections(body: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^## ", body)
    out = [("概述", parts[0].strip())] if parts[0].strip() else []
    for p in parts[1:]:
        title, _, content = p.partition("\n")
        out.append((title.strip(), content.strip()))
    return out


class MetricDocRetriever:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.docs: dict[str, str] = {}
        self.meta: dict[str, dict] = {}
        self.chunks: list[dict] = []
        for p in sorted(self.folder.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            meta, body = _split_front_matter(text)
            mid = meta.get("metric_id", p.stem)
            self.docs[mid] = text
            self.meta[mid] = meta
            head = f"{mid} {meta.get('name_cn', '')} " + " ".join(ALIASES.get(mid, []))
            for title, content in _sections(body):
                # 小节标题重复 3 次，相当于给标题加权：问「常见错误」时优先命中那一节
                toks = tokenize(head) + tokenize(title) * 3 + tokenize(content)
                self.chunks.append({"metric_id": mid, "section": title, "text": content, "tokens": toks})
        self._build_index()

    def _build_index(self) -> None:
        self.tf = [Counter(c["tokens"]) for c in self.chunks]
        self.len = [len(c["tokens"]) for c in self.chunks]
        self.avg_len = (sum(self.len) / len(self.len)) if self.len else 1.0
        df = Counter(t for tf in self.tf for t in tf)
        n = len(self.chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def _score(self, q: list[str], i: int) -> float:
        tf, dl, s = self.tf[i], self.len[i], 0.0
        for t in q:
            f = tf.get(t, 0)
            if f:
                s += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avg_len))
        return s

    def search_chunks(self, query: str, top_k: int = 3) -> list[dict]:
        q = tokenize(query)
        # 别名命中时，把对应 metric_id 也加进查询，相当于做了一次查询扩展
        for mid, words in ALIASES.items():
            if any(w in query.lower() for w in words) or mid in query.lower():
                q.append(mid)
        scored = [(self._score(q, i), i) for i in range(len(self.chunks))]
        scored = [x for x in scored if x[0] > 0]
        scored.sort(reverse=True)
        return [{**{k: v for k, v in self.chunks[i].items() if k != "tokens"}, "score": round(s, 3)}
                for s, i in scored[:top_k]]

    def search_metric_ids(self, query: str, top_k: int = 3) -> list[str]:
        """文档级排序：每篇取其最好的小节分数。评测检索命中率时用这个。"""
        best: dict[str, float] = {}
        for c in self.search_chunks(query, top_k=len(self.chunks)):
            best[c["metric_id"]] = max(best.get(c["metric_id"], 0.0), c["score"])
        return sorted(best, key=best.get, reverse=True)[:top_k]

    def search(self, query: str, top_k: int = 3) -> str:
        """给 MCP 工具用的文本格式：命中的小节 + 出处。"""
        hits = self.search_chunks(query, top_k)
        if not hits:
            return f"没有检索到相关口径。可用指标：{', '.join(self.docs)}"
        return "\n\n---\n\n".join(
            f"[{h['metric_id']} § {h['section']}] score={h['score']}\n{h['text']}" for h in hits)

    def get(self, metric_id: str) -> str:
        return self.docs.get(metric_id, f"未找到 {metric_id}，可用：{', '.join(self.docs)}")

    def list_metrics(self) -> list[dict]:
        return [{"metric_id": k, "name_cn": m.get("name_cn", ""), "level": m.get("level", ""),
                 "parent": m.get("parent", "")} for k, m in self.meta.items()]
