"""
情景记忆模块。
每轮对话结束后异步提取有意义的事件，存入 SQLite + ChromaDB。
检索时按语义相似度 + 时间近因性返回相关事件。
"""

import os
import json
import asyncio
from datetime import datetime
from sqlalchemy import select
from app.db.database import async_session, init_db
from app.models.episodic_event import EpisodicEvent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

EPISODIC_COLLECTION = "episodic_events"

EXTRACT_PROMPT = """分析以下对话，判断是否产生了值得长期记住的事件。

值得记住的事件类型：
- intent: 客户表达了明确意向（想买/想卖/想了解某产品）
- follow_up: 完成了客户跟进（打电话/发微信/见面）
- decision: 做出了决策或推荐（推荐了某基金/调整了配置）
- feedback: 客户给出了反馈（满意/不满/拒绝）

如果没有有意义的事件，返回空 JSON 数组 []。
如果有，返回 JSON 数组，每个元素格式：
{"content": "事件描述（一句话）", "event_type": "类型", "entities": ["涉及的实体"], "importance": 0.0-1.0}

只返回 JSON，不要其他内容。"""


def _get_episodic_collection():
    """获取或创建情景记忆的 ChromaDB collection。"""
    import chromadb
    client = chromadb.PersistentClient(path="./chroma_data")
    return client.get_or_create_collection(EPISODIC_COLLECTION)


async def extract_and_store_events(
    user_id: str,
    conversation_id: str,
    user_message: str,
    assistant_reply: str,
):
    """
    异步提取事件并存储。在 ai_agent.py 返回响应后调用。
    """
    events = await _extract_events(user_message, assistant_reply)
    if not events:
        return

    async with async_session() as session:
        for event in events:
            # 存 SQLite
            record = EpisodicEvent(
                user_id=user_id,
                conversation_id=conversation_id,
                content=event["content"],
                event_type=event["event_type"],
                entities=json.dumps(event.get("entities", []), ensure_ascii=False),
                importance=event.get("importance", 0.5),
            )
            session.add(record)
            await session.flush()

            # 存 ChromaDB（向量化）
            _embed_event(record.id, event["content"], {
                "user_id": user_id,
                "event_type": event["event_type"],
                "entities": json.dumps(event.get("entities", []), ensure_ascii=False),
                "importance": event.get("importance", 0.5),
                "timestamp": datetime.now().isoformat(),
            })

        await session.commit()


async def retrieve_episodic_events(user_id: str, query: str, limit: int = 3) -> list[dict]:
    """
    检索与当前问题相关的历史事件。
    返回 [{"content": "...", "event_type": "...", "timestamp": "...", "importance": ...}]
    """
    collection = _get_episodic_collection()

    try:
        results = collection.query(
            query_texts=[query],
            n_results=limit * 2,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        # where filter 可能不支持，fallback 到无过滤
        results = collection.query(
            query_texts=[query],
            n_results=limit * 2,
            include=["documents", "metadatas", "distances"],
        )

    if not results["documents"] or not results["documents"][0]:
        return []

    events = []
    for i, (doc, meta, dist) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    )):
        # 过滤非当前用户的（如果 where 不生效）
        if meta.get("user_id") != user_id:
            continue

        similarity = 1.0 / (1.0 + dist)
        importance = meta.get("importance", 0.5)

        # 时间衰减
        timestamp_str = meta.get("timestamp", "")
        recency = _calculate_recency(timestamp_str)

        # 综合评分：(相似度×0.8 + 时间近因性×0.2) × 重要性权重
        score = (similarity * 0.8 + recency * 0.2) * (0.8 + importance * 0.4)

        events.append({
            "content": doc,
            "event_type": meta.get("event_type", ""),
            "timestamp": timestamp_str,
            "importance": importance,
            "score": score,
        })

    # 按分数排序，取 top N
    events.sort(key=lambda x: x["score"], reverse=True)
    return events[:limit]


def _embed_event(event_id: int, content: str, metadata: dict):
    """将事件向量化存入 ChromaDB。"""
    collection = _get_episodic_collection()
    collection.upsert(
        ids=[f"event_{event_id}"],
        documents=[content],
        metadatas=[metadata],
    )


def _calculate_recency(timestamp_str: str) -> float:
    """计算时间近因性，越近分越高。"""
    if not timestamp_str:
        return 0.5
    try:
        event_time = datetime.fromisoformat(timestamp_str)
        hours_ago = (datetime.now() - event_time).total_seconds() / 3600
        import math
        return max(0.1, math.exp(-0.05 * hours_ago))
    except Exception:
        return 0.5


async def _extract_events(user_message: str, assistant_reply: str) -> list[dict]:
    """用 LLM 从对话中提取事件。"""
    if not OPENAI_API_KEY:
        return _rule_based_extract(user_message, assistant_reply)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

        conversation = f"用户: {user_message}\n助手: {assistant_reply}"

        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": conversation},
            ],
            max_tokens=200,
            temperature=0,
        )

        content = response.choices[0].message.content or "[]"
        # 清理可能的 markdown 包裹
        content = content.strip().strip("`").replace("json", "").strip()
        events = json.loads(content)

        if isinstance(events, list):
            return [e for e in events if isinstance(e, dict) and "content" in e]
        return []

    except Exception:
        return _rule_based_extract(user_message, assistant_reply)


def _rule_based_extract(user_message: str, assistant_reply: str) -> list[dict]:
    """LLM 不可用时的降级方案：关键词规则提取。"""
    events = []

    # 跟进记录
    if any(k in user_message for k in ["聊了", "打了电话", "发了微信", "见了面", "沟通"]):
        events.append({
            "content": user_message[:80],
            "event_type": "follow_up",
            "entities": [],
            "importance": 0.7,
        })

    # 明确意向
    if any(k in user_message for k in ["想买", "想卖", "感兴趣", "认购", "申购"]):
        events.append({
            "content": user_message[:80],
            "event_type": "intent",
            "entities": [],
            "importance": 0.8,
        })

    # 推荐决策
    if "推荐" in assistant_reply and any(k in assistant_reply for k in ["建议", "适合"]):
        events.append({
            "content": f"向客户推荐了产品：{assistant_reply[:60]}",
            "event_type": "decision",
            "entities": [],
            "importance": 0.6,
        })

    return events
