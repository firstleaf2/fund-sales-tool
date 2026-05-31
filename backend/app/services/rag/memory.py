"""
会话记忆管理。
从 SQLite 加载历史消息，滑动窗口裁剪，超出时压缩为摘要。
"""

import os
from sqlalchemy import select
from app.db.database import async_session
from app.models.chat_message import ChatMessage

MAX_TURNS = 10
MAX_SUMMARY_TURNS = 5


async def save_message(user_id: str, conversation_id: str, role: str, content: str):
    """保存一条消息到数据库。"""
    async with async_session() as session:
        msg = ChatMessage(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        session.add(msg)
        await session.commit()


async def get_history(conversation_id: str) -> list[dict]:
    """
    获取会话历史，已做滑动窗口裁剪。
    返回 [{"role": "user", "content": "..."}, ...] 格式，可直接拼入 LLM messages。
    """
    async with async_session() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        messages = result.scalars().all()

    if not messages:
        return []

    # 转为 dict 列表
    history = [{"role": m.role, "content": m.content} for m in messages]

    # 按轮计算（一轮 = user + assistant）
    turns = len(history) // 2

    if turns <= MAX_TURNS:
        return history

    # 超出 MAX_TURNS：压缩最早的部分为摘要
    # 保留最近 MAX_TURNS 轮（2 * MAX_TURNS 条消息）
    keep_count = MAX_TURNS * 2
    old_messages = history[:-keep_count]
    recent_messages = history[-keep_count:]

    # 生成摘要
    summary = await _summarize(old_messages)

    if summary:
        return [{"role": "system", "content": f"之前的对话摘要：{summary}"}] + recent_messages
    return recent_messages


async def _summarize(messages: list[dict]) -> str:
    """用 LLM 压缩旧消息为一句摘要。"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        # 无 API key 时简单拼接
        parts = []
        for m in messages:
            if m["role"] == "user":
                parts.append(f"用户问了：{m['content'][:30]}")
        return "；".join(parts[-3:])

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        conversation_text = "\n".join(
            f"{m['role']}: {m['content']}" for m in messages
        )

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "将以下对话压缩为一句话摘要，保留关键信息（提到的客户名、基金名、决策结论）。只返回摘要，不超过100字。"},
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=100,
            temperature=0,
        )
        return response.choices[0].message.content or ""
    except Exception:
        parts = []
        for m in messages:
            if m["role"] == "user":
                parts.append(m["content"][:30])
        return "之前讨论了：" + "、".join(parts[-3:])
