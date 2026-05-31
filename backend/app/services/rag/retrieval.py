from app.services.rag.vector_store import search_funds, search_customers
from app.services.rag.intent import Intent

RAG_CONFIDENCE_THRESHOLD = 0.4


def retrieve_context(query: str, intent: Intent) -> dict:
    """
    根据意图检索上下文。
    返回 {"context": str, "confident": bool, "sources": list}
    confident=False 时表示 RAG 结果不可靠，需要 fallback 到 Function Calling。
    """
    if intent == Intent.CHAT:
        return {"context": "", "confident": True, "sources": []}

    context_parts = []
    sources = []
    max_score = 0.0

    if intent in (Intent.RECOMMEND, Intent.FUND_QUERY, Intent.MARKET):
        fund_results = search_funds(query, n_results=5)
        if fund_results:
            max_score = max(max_score, max(r["score"] for r in fund_results))
            context_parts.append("## 相关基金产品信息\n")
            for item in fund_results:
                context_parts.append(f"- {item['document']}\n")
                sources.append({
                    "type": "fund",
                    "id": item["metadata"].get("fund_id", 0),
                    "name": item["document"].split(" (")[0] if " (" in item["document"] else "基金",
                })

    if intent in (Intent.RECOMMEND, Intent.CUSTOMER_QUERY):
        customer_results = search_customers(query, n_results=3)
        if customer_results:
            max_score = max(max_score, max(r["score"] for r in customer_results))
            context_parts.append("\n## 相关客户信息\n")
            for item in customer_results:
                context_parts.append(f"- {item['document']}\n")
                doc = item["document"]
                name = doc.split("客户:")[1].split(" -")[0] if "客户:" in doc else "客户"
                sources.append({
                    "type": "customer",
                    "id": item["metadata"].get("customer_id", 0),
                    "name": name,
                })

    context = "".join(context_parts) if context_parts else ""
    confident = max_score >= RAG_CONFIDENCE_THRESHOLD

    return {"context": context, "confident": confident, "sources": sources}
