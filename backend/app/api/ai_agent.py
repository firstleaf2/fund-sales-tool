from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.database import get_db
from app.models.chat_message import ChatMessage
from app.schemas.ai import ChatRequest, ChatResponse, SourceItem, ChartData
from app.services.rag.generation import generate_response
from app.services.rag.memory import save_message, get_history

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    user_id = request.user_id or "anonymous"

    history = await get_history(request.conversation_id) if request.conversation_id else []

    result = await generate_response(
        message=request.message,
        conversation_id=request.conversation_id,
        history=history,
    )

    conversation_id = result["conversation_id"]

    await save_message(user_id, conversation_id, "user", request.message)
    await save_message(user_id, conversation_id, "assistant", result["reply"])

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
