import asyncio
import json as json_lib
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.database import get_db
from app.models.chat_message import ChatMessage
from app.schemas.ai import ChatRequest, ChatResponse, SourceItem, ChartData
from app.services.rag.generation import generate_response, generate_response_stream
from app.services.rag.memory import save_message, get_history
from app.services.rag.episodic_memory import extract_and_store_events, retrieve_episodic_events
from app.services.rag.semantic_memory import retrieve_semantic_knowledge, consolidate_semantic_memory

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_id = request.user_id or "anonymous"

    # 获取工作记忆（历史对话原文）
    history = await get_history(request.conversation_id) if request.conversation_id else []

    # 检索情景记忆（相关历史事件）
    episodic_events = await retrieve_episodic_events(user_id, request.message, limit=3)

    # 检索语义记忆（抽象知识）
    semantic_knowledge = await retrieve_semantic_knowledge(user_id, request.message, limit=3)

    # 拼接记忆上下文
    memory_context_parts = []
    if semantic_knowledge:
        memory_context_parts.append("[长期知识记忆]")
        for sk in semantic_knowledge:
            memory_context_parts.append(f"- {sk['knowledge']}")
    if episodic_events:
        memory_context_parts.append("[历史事件记忆]")
        for ev in episodic_events:
            memory_context_parts.append(f"- [{ev['event_type']}] {ev['content']} ({ev['timestamp'][:10]})")

    memory_context = "\n".join(memory_context_parts)

    # 生成回复
    result = await generate_response(
        message=request.message,
        conversation_id=request.conversation_id,
        history=history,
        episodic_context=memory_context,
    )

    conversation_id = result["conversation_id"]

    # 保存对话原文（如果有图表，把 option JSON 也存进去，方便追问修改）
    await save_message(user_id, conversation_id, "user", request.message)
    chart_data = result.get("chart")
    reply_to_save = result["reply"]
    if chart_data and chart_data.get("option"):
        reply_to_save += f"\n\n[上次生成的图表配置]\n```chart-json\n{json_lib.dumps(chart_data['option'], ensure_ascii=False)}\n```"
    await save_message(user_id, conversation_id, "assistant", reply_to_save)

    # 异步：提取情景记忆 + 尝试归纳语义记忆
    asyncio.create_task(
        _post_chat_tasks(user_id, conversation_id, request.message, result["reply"])
    )

    chart_data = result.get("chart")
    chart = ChartData(**chart_data) if chart_data else None

    return ChatResponse(
        reply=result["reply"],
        sources=[SourceItem(**s) for s in result["sources"]],
        conversation_id=conversation_id,
        chart=chart,
    )


async def _post_chat_tasks(user_id: str, conversation_id: str, user_message: str, assistant_reply: str):
    """对话结束后的异步任务：提取情景记忆 + 尝试归纳语义记忆。"""
    await extract_and_store_events(user_id, conversation_id, user_message, assistant_reply)
    await consolidate_semantic_memory(user_id, min_events=3)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE 流式对话接口。"""
    user_id = request.user_id or "anonymous"

    history = await get_history(request.conversation_id) if request.conversation_id else []

    episodic_events = await retrieve_episodic_events(user_id, request.message, limit=3)
    semantic_knowledge = await retrieve_semantic_knowledge(user_id, request.message, limit=3)

    memory_context_parts = []
    if semantic_knowledge:
        memory_context_parts.append("[长期知识记忆]")
        for sk in semantic_knowledge:
            memory_context_parts.append(f"- {sk['knowledge']}")
    if episodic_events:
        memory_context_parts.append("[历史事件记忆]")
        for ev in episodic_events:
            memory_context_parts.append(f"- [{ev['event_type']}] {ev['content']} ({ev['timestamp'][:10]})")
    memory_context = "\n".join(memory_context_parts)

    async def event_generator():
        full_reply = ""
        conversation_id = request.conversation_id

        async for chunk in generate_response_stream(
            message=request.message,
            conversation_id=request.conversation_id,
            history=history,
            episodic_context=memory_context,
        ):
            if chunk["type"] == "meta":
                conversation_id = chunk["conversation_id"]
                yield f"data: {json_lib.dumps({'type': 'meta', 'sources': chunk['sources'], 'conversation_id': conversation_id}, ensure_ascii=False)}\n\n"
            elif chunk["type"] == "content":
                full_reply += chunk["data"]
                yield f"data: {json_lib.dumps({'type': 'content', 'data': chunk['data']}, ensure_ascii=False)}\n\n"
            elif chunk["type"] == "done":
                yield f"data: {json_lib.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

        # 流结束后保存消息和提取记忆
        if conversation_id and full_reply:
            await save_message(user_id, conversation_id, "user", request.message)
            await save_message(user_id, conversation_id, "assistant", full_reply)
            asyncio.create_task(_post_chat_tasks(user_id, conversation_id, request.message, full_reply))

    return StreamingResponse(event_generator(), media_type="text/event-stream")

    chart_data = result.get("chart")
    chart = ChartData(**chart_data) if chart_data else None

    return ChatResponse(
        reply=result["reply"],
        sources=[SourceItem(**s) for s in result["sources"]],
        conversation_id=conversation_id,
        chart=chart,
    )


@router.get("/messages")
async def get_messages(
    conversation_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取某个会话的历史消息。"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return {
        "data": [
            {"role": m.role, "content": m.content, "created_at": str(m.created_at)}
            for m in messages
        ]
    }


@router.get("/conversations")
async def get_conversations(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的会话列表（最近的排前面）。"""
    result = await db.execute(
        select(ChatMessage.conversation_id, ChatMessage.content, ChatMessage.created_at)
        .where(ChatMessage.user_id == user_id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc())
    )
    rows = result.all()

    # 按 conversation_id 去重，取每个会话的第一条消息作为标题
    seen = set()
    conversations = []
    for row in rows:
        cid = row[0]
        if cid not in seen:
            seen.add(cid)
            conversations.append({
                "conversation_id": cid,
                "title": row[1][:30],
                "last_time": str(row[2]),
            })
    return {"data": conversations[:20]}
