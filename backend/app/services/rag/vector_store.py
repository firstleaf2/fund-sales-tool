import chromadb

_client = None
FUND_COLLECTION = "fund_documents"
CUSTOMER_COLLECTION = "customer_profiles"


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path="./chroma_data")
    return _client


def get_fund_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(FUND_COLLECTION)


def get_customer_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(CUSTOMER_COLLECTION)


def embed_fund(fund_id: int, code: str, name: str, fund_type: str, risk_level: str, manager: str, description: str):
    collection = get_fund_collection()
    doc = f"{name} ({code}) - {fund_type}型基金 - 风险等级:{risk_level} - 基金经理:{manager} - {description}"
    collection.upsert(
        ids=[f"fund_{fund_id}"],
        documents=[doc],
        metadatas=[{"fund_id": fund_id, "code": code, "type": fund_type, "risk_level": risk_level}],
    )


def embed_customer(customer_id: int, name: str, risk_preference: str, holdings_summary: str):
    collection = get_customer_collection()
    doc = f"客户:{name} - 风险偏好:{risk_preference} - 持仓:{holdings_summary}"
    collection.upsert(
        ids=[f"customer_{customer_id}"],
        documents=[doc],
        metadatas=[{"customer_id": customer_id, "risk_preference": risk_preference}],
    )


def search_funds(query: str, n_results: int = 5) -> list[dict]:
    collection = get_fund_collection()
    results = collection.query(query_texts=[query], n_results=n_results, include=["documents", "metadatas", "distances"])
    items = []
    if results["documents"] and results["metadatas"]:
        distances = results.get("distances", [[]])[0]
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            # ChromaDB 返回的是 L2 距离，转换为相似度分数（越大越相似）
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 / (1.0 + distance)
            items.append({"document": doc, "metadata": meta, "score": similarity})
    return items


def search_customers(query: str, n_results: int = 3) -> list[dict]:
    collection = get_customer_collection()
    results = collection.query(query_texts=[query], n_results=n_results, include=["documents", "metadatas", "distances"])
    items = []
    if results["documents"] and results["metadatas"]:
        distances = results.get("distances", [[]])[0]
        for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
            distance = distances[i] if i < len(distances) else 1.0
            similarity = 1.0 / (1.0 + distance)
            items.append({"document": doc, "metadata": meta, "score": similarity})
    return items
