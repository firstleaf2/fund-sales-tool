"""
混合检索 + 重排模块。
- 多路召回：向量检索 + BM25 关键词检索
- 融合：RRF (Reciprocal Rank Fusion) 合并两路结果
- 重排：基于 metadata 规则精排
"""

import math
import re
from collections import defaultdict
from app.services.rag.vector_store import search_funds, search_customers
from app.services.rag.intent import Intent


# ============================================================
# BM25 实现（轻量版，不依赖外部库）
# ============================================================

class BM25:
    """简易 BM25，对内存中的文档集做关键词检索。"""

    def __init__(self, documents: list[dict], k1: float = 1.5, b: float = 0.75):
        self.docs = documents
        self.k1 = k1
        self.b = b
        self.doc_count = len(documents)
        self.avg_dl = 0.0
        self.doc_lengths: list[int] = []
        self.term_freqs: list[dict[str, int]] = []
        self.doc_freq: dict[str, int] = defaultdict(int)

        for doc in documents:
            tokens = self._tokenize(doc["document"])
            self.doc_lengths.append(len(tokens))
            tf: dict[str, int] = defaultdict(int)
            for t in tokens:
                tf[t] += 1
            self.term_freqs.append(dict(tf))
            for t in set(tokens):
                self.doc_freq[t] += 1

        self.avg_dl = sum(self.doc_lengths) / self.doc_count if self.doc_count > 0 else 1.0

    def _tokenize(self, text: str) -> list[str]:
        """中文按字切分 + 保留连续英文/数字作为整体 token。"""
        tokens = []
        for segment in re.findall(r'[a-zA-Z0-9]+|[一-鿿]', text):
            tokens.append(segment.lower())
        return tokens

    def search(self, query: str, top_n: int = 10) -> list[dict]:
        query_tokens = self._tokenize(query)
        scores: list[float] = []

        for i in range(self.doc_count):
            score = 0.0
            dl = self.doc_lengths[i]
            for term in query_tokens:
                if term not in self.term_freqs[i]:
                    continue
                tf = self.term_freqs[i][term]
                df = self.doc_freq.get(term, 0)
                idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avg_dl)
                score += idf * numerator / denominator
            scores.append(score)

        ranked = sorted(range(self.doc_count), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked[:top_n]:
            if scores[idx] > 0:
                results.append({**self.docs[idx], "bm25_score": scores[idx]})
        return results


# ============================================================
# 多路召回 + RRF 融合
# ============================================================

def _rrf_fusion(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    """
    Reciprocal Rank Fusion：合并两路检索结果。
    每条文档的融合分数 = sum(1 / (k + rank_in_each_list))
    """
    doc_scores: dict[str, float] = defaultdict(float)
    doc_map: dict[str, dict] = {}

    for rank, item in enumerate(vector_results):
        doc_id = _doc_id(item)
        doc_scores[doc_id] += 1.0 / (k + rank + 1)
        doc_map[doc_id] = item

    for rank, item in enumerate(bm25_results):
        doc_id = _doc_id(item)
        doc_scores[doc_id] += 1.0 / (k + rank + 1)
        if doc_id not in doc_map:
            doc_map[doc_id] = item

    sorted_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)
    return [{**doc_map[did], "rrf_score": doc_scores[did]} for did in sorted_ids]


def _doc_id(item: dict) -> str:
    meta = item.get("metadata", {})
    if "fund_id" in meta:
        return f"fund_{meta['fund_id']}"
    if "customer_id" in meta:
        return f"customer_{meta['customer_id']}"
    return item.get("document", "")[:50]


# ============================================================
# 重排（规则 + 意图匹配）
# ============================================================

def _rerank(results: list[dict], intent: Intent, query: str) -> list[dict]:
    """
    基于业务规则重排：
    - RECOMMEND 意图：风险等级匹配的基金排前面
    - FUND_QUERY 意图：名称/代码精确匹配的排前面
    - CUSTOMER_QUERY 意图：姓名精确匹配的排前面
    """
    for item in results:
        boost = 0.0
        meta = item.get("metadata", {})
        doc = item.get("document", "")

        if intent == Intent.RECOMMEND:
            # 如果 query 里提到了风险偏好关键词，匹配的基金加分
            if "保守" in query and meta.get("risk_level") == "low":
                boost += 0.3
            elif "稳健" in query and meta.get("risk_level") == "medium":
                boost += 0.3
            elif "激进" in query and meta.get("risk_level") == "high":
                boost += 0.3

        elif intent == Intent.FUND_QUERY:
            # 名称或代码精确出现在 query 中
            if meta.get("code") and meta["code"] in query:
                boost += 0.5
            fund_name = doc.split(" (")[0] if " (" in doc else ""
            if fund_name and fund_name in query:
                boost += 0.5

        elif intent == Intent.CUSTOMER_QUERY:
            # 客户姓名精确匹配
            if "客户:" in doc:
                name = doc.split("客户:")[1].split(" -")[0]
                if name in query:
                    boost += 0.5

        item["final_score"] = item.get("rrf_score", 0) + boost

    results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    return results


# ============================================================
# 对外接口
# ============================================================

# 缓存 BM25 索引（启动后第一次调用时构建）
_fund_bm25: BM25 | None = None
_customer_bm25: BM25 | None = None


def _get_fund_bm25() -> BM25:
    global _fund_bm25
    if _fund_bm25 is None:
        # 从向量库拉全量文档构建 BM25 索引
        all_funds = search_funds("", n_results=100)
        _fund_bm25 = BM25(all_funds)
    return _fund_bm25


def _get_customer_bm25() -> BM25:
    global _customer_bm25
    if _customer_bm25 is None:
        all_customers = search_customers("", n_results=100)
        _customer_bm25 = BM25(all_customers)
    return _customer_bm25


def hybrid_retrieve(query: str, intent: Intent, top_n: int = 5) -> dict:
    """
    混合检索 + 重排。
    返回 {"results": list[dict], "max_score": float, "confident": bool}
    """
    RAG_CONFIDENCE_THRESHOLD = 0.4

    if intent == Intent.CHAT:
        return {"results": [], "max_score": 0.0, "confident": True}

    all_results = []

    if intent in (Intent.RECOMMEND, Intent.FUND_QUERY, Intent.MARKET):
        # 向量检索
        vector_results = search_funds(query, n_results=top_n * 2)
        # BM25 检索
        bm25_results = _get_fund_bm25().search(query, top_n=top_n * 2)
        # RRF 融合
        fused = _rrf_fusion(vector_results, bm25_results)
        all_results.extend(fused)

    if intent in (Intent.RECOMMEND, Intent.CUSTOMER_QUERY):
        vector_results = search_customers(query, n_results=top_n)
        bm25_results = _get_customer_bm25().search(query, top_n=top_n)
        fused = _rrf_fusion(vector_results, bm25_results)
        all_results.extend(fused)

    # 重排
    reranked = _rerank(all_results, intent, query)[:top_n]

    # 置信度：取向量检索的最高分判断
    max_score = max((r.get("score", 0) for r in all_results), default=0.0)
    confident = max_score >= RAG_CONFIDENCE_THRESHOLD

    return {"results": reranked, "max_score": max_score, "confident": confident}
