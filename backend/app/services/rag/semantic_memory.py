"""
语义记忆模块。
定期从情景记忆中归纳抽象知识，存入 ChromaDB。
检索时返回与当前问题相关的长期知识。
"""

import os
import json
import math
from datetime import datetime
from sqlalchemy import select, func
from app.db.database import async_session
from app.models.episodic_event import EpisodicEvent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SEMANTIC_COLLECTION = "semantic_knowledge"

CONSOLIDATE_PROMPT = """你是一个知识提炼器。根据以下关于同一实体的多条历史事件，归纳出一条抽象的、长期有效的知识。

要求：
- 输出一句话，描述这个实体的稳定特征或规律
- 不要包含具体日期
- 不要重复事件细节，要提炼本质
- 如果事件之间有矛盾，以最新的为准

示例：
事件：["李明想买债券基金", "李明拒绝了股票基金", "李明说只要低风险的"]
输出：{"knowledge": "李明是保守型投资者，只接受低风险产品（债券型、货币型）", "entity": "李明", "importance": 0.9}

只返回一个 JSON 对象，不要其他内容。"""


def _get_semantic_collection():
    """获取或创建语义记忆的 ChromaDB collection。"""
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_data")
    return client.get_or_create_collection(SEMANTIC_COLLECTION)


async def consolidate_semantic_memory(user_id: str, min_events: int = 3):
    """
    从情景记忆中归纳语义记忆。
    扫描同一实体出现 >= min_events 次的情况，归纳为抽象知识。
    """
    # 1. 从 SQLite 拉所有情景事件
    async with async_session() as session:
        result = await session.execute(
            select(EpisodicEvent).where(EpisodicEvent.user_id == user_id)
        )
        events = result.scalars().all()

    if not events:
        return 0

    # 2. 按实体聚合
    entity_events: dict[str, list[str]] = {}
    for ev in events:
        entities = json.loads(ev.entities) if ev.entities else []
        for entity in entities:
            if entity not in entity_events:
                entity_events[entity] = []
            entity_events[entity].append(ev.content)

    # 3. 对出现次数 >= min_events 的实体做归纳
    consolidated_count = 0
    collection = _get_semantic_collection()

    for entity, event_contents in entity_events.items():
        if len(event_contents) < min_events:
            continue

        # 检查是否已有该实体的语义记忆
        existing = collection.get(ids=[f"semantic_{user_id}_{entity}"])
        if existing and existing["ids"]:
            # 已存在，检查事件数是否增加了（需要更新）
            old_count = 0
            if existing["metadatas"]:
                old_count = existing["metadatas"][0].get("event_count", 0)
            if len(event_contents) <= old_count:
                continue  # 没有新事件，跳过

        # LLM 归纳
        knowledge = await _consolidate_entity(entity, event_contents)
        if not knowledge:
            continue

        # 写入 ChromaDB
        collection.upsert(
            ids=[f"semantic_{user_id}_{entity}"],
            documents=[knowledge["knowledge"]],
            metadatas=[{
                "user_id": user_id,
                "entity": entity,
                "importance": knowledge.get("importance", 0.7),
                "event_count": len(event_contents),
                "updated_at": datetime.now().isoformat(),
            }],
        )
        consolidated_count += 1

    return consolidated_count


async def retrieve_semantic_knowledge(user_id: str, query: str, limit: int = 3) -> list[dict]:
    """
    检索与当前问题相关的语义知识。
    返回 [{"knowledge": "...", "entity": "...", "importance": ..., "score": ...}]
    """
    collection = _get_semantic_collection()

    if collection.count() == 0:
        return []

    try:
        results = collection.query(
            query_texts=[query],
            n_results=limit * 2,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=[query],
            n_results=limit * 2,
            include=["documents", "metadatas", "distances"],
        )

    if not results["documents"] or not results["documents"][0]:
        return []

    knowledge_items = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        if meta.get("user_id") != user_id:
            continue

        similarity = 1.0 / (1.0 + dist)
        importance = meta.get("importance", 0.7)

        # 语义记忆不做时间衰减（是"永真"的知识）
        # 评分：相似度 × 重要性权重
        score = similarity * (0.8 + importance * 0.4)

        knowledge_items.append({
            "knowledge": doc,
            "entity": meta.get("entity", ""),
            "importance": importance,
            "score": score,
        })

    knowledge_items.sort(key=lambda x: x["score"], reverse=True)
    return knowledge_items[:limit]


async def _consolidate_entity(entity: str, event_contents: list[str]) -> dict | None:
    """用 LLM 归纳一个实体的语义知识。"""
    if not OPENAI_API_KEY:
        # 降级：简单拼接
        return {
            "knowledge": f"{entity}相关：{'；'.join(event_contents[-3:])}",
            "entity": entity,
            "importance": 0.6,
        }

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": CONSOLIDATE_PROMPT},
                {"role": "user", "content": f"实体：{entity}\n事件：{json.dumps(event_contents[-5:], ensure_ascii=False)}"},
            ],
            max_tokens=150,
            temperature=0,
        )

        content = response.choices[0].message.content or ""
        content = content.strip().strip("`").replace("json", "").strip()
        result = json.loads(content)

        if isinstance(result, dict) and "knowledge" in result:
            result["entity"] = entity
            return result
        return None

    except Exception:
        return {
            "knowledge": f"{entity}相关：{'；'.join(event_contents[-3:])}",
            "entity": entity,
            "importance": 0.6,
        }
